"""Queuing room groups so each keeps its own settings (issue #72).

THE REPORTER'S USE CASE, in their words: "I typically let it vacuum twice before
mopping... if today I would like to execute this sequence for room A and room B, and
tomorrow for room A and room C. Profile doesn't work well in this use case. I will have
to create a profile for each room."

That is N room groups in one run, each carrying its own per-room settings, with the set
of rooms changing day to day.

THIS WAS HALF-BUILT, NOT MISSING, and that is what made it worth fixing rather than
designing. `ProfileManager`'s `has_stops` already declared `len(room_group_steps) > 1`
to be a sequenced run; the card mirrored that rule, routed Start through the stepped
path, previewed "Clean A -> Clean B" and shipped a chip that appends a second room
group. All three gates that actually EXECUTE asked only "does this contain a
charge_wait/wait/zone". So a user could author exactly this issue, watch the card
promise it, and watch the run go flat with every group's settings discarded.

The three gates, all now asking `plan_is_sequenced`:
  1. the stash        — `profiles/manager.py::start_run_profile`
  2. the stepped path — `planning/run_plan.py::_build_effective_start_plan` (twice)
  3. **the collapse** — `planning/run_plan.py::_build_steps_phases`, which rebuilt N
     room_group phases into ONE atomic dispatch whenever there was no break and no
     zone. This is the one a patch that opened only the gates would miss: it would look
     right, pass, and still run flat.

Coverage targets
----------------
[QRG-1] two room groups with NO break stay two phases, each with its own rooms.
[QRG-2] one room group is still one atomic clean — the no-cost guard.
[QRG-3] each group keeps its OWN per-room settings; the overlay is what the collapse
        used to discard, so identical ids with merged settings would be a false pass.
[QRG-4] three groups stay three, in authored order.
[QRG-5] the backend's `has_stops` and the executing gates now agree, which is the
        disagreement that produced the bug.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.step_types import (
    plan_is_sequenced,
    plan_requires_stepped_execution,
)

from tests._factories import MAP as _MAP, VAC as _VAC


def _rg(*rooms, **settings):
    """A room_group step; settings ride on each room, as the card writes them."""
    return {
        "type": "room_group",
        "rooms": [{"room_id": r, **settings} for r in rooms],
    }


def _phases(manager, monkeypatch, steps, included):
    """Materialize steps -> phases, spying on the REAL call the builder makes.

    `_build_dispatch_phases` needs a brand engine, so it is replaced — but with a spy
    that records its ACTUAL arguments (`queue_room_ids` and `managed_rooms`) rather
    than a hand-invented phase shape. Those two are the contract: the ids say how the
    run was divided, and `managed_rooms` carries each group's settings overlay, which
    is precisely what the collapse used to discard.
    """
    monkeypatch.setattr(
        manager.run_plan, "_build_dispatch_phases",
        lambda **kw: [{
            "phase_type": "room",
            "ids": list(kw["queue_room_ids"]),
            "queue_room_ids": list(kw["queue_room_ids"]),
            "managed_rooms": dict(kw["managed_rooms"]),
        }],
    )
    return manager.run_plan._build_steps_phases(
        vacuum_entity_id=_VAC, map_id=_MAP, effective_rooms={},
        included_room_ids=set(included), run_steps=steps, strict_order=False,
    )


def _setting(phase, room_id, field):
    return (phase["managed_rooms"].get(str(room_id)) or {}).get(field)


async def test_qrg_1_two_groups_with_no_break_stay_two_phases(hass, manager, monkeypatch):
    """[QRG-1] THE ISSUE. "Clean A, then clean B" with nothing between them.

    Before: one atomic clean over {1,2}. The card said otherwise.
    """
    phases = _phases(manager, monkeypatch, [_rg(1), _rg(2)], included={1, 2})

    assert [p["ids"] for p in phases] == [[1], [2]], (
        "two authored groups collapsed into one clean — the sequence the card promised "
        "did not happen"
    )


async def test_qrg_2_one_group_is_still_one_atomic_clean(hass, manager, monkeypatch):
    """[QRG-2] THE NO-COST GUARD. A plain run must not become multi-phase.

    Without this, QRG-1 is satisfied by never collapsing anything, and every ordinary
    one-group run pays for phase machinery it does not need.
    """
    phases = _phases(manager, monkeypatch, [_rg(1, 2, 3)], included={1, 2, 3})

    assert len(phases) == 1
    assert phases[0]["ids"] == [1, 2, 3]


async def test_qrg_3_each_group_keeps_its_own_settings(hass, manager, monkeypatch):
    """[QRG-3] THE POINT, and the assertion that cannot be faked by ids alone.

    The reporter wants "vacuum twice" then "mop" — two groups over the same room with
    DIFFERENT settings. The collapse rebuilt the phases from a flat id list, so the ids
    could look right while every group's overlay was gone. Asserting ids only would
    have passed against the old behaviour for the single-room case.
    """
    steps = [
        _rg(1, clean_mode="vacuum", clean_passes=2),
        _rg(1, clean_mode="mop", clean_passes=1),
    ]

    phases = _phases(manager, monkeypatch, steps, included={1})

    assert len(phases) == 2, "the two passes merged into one"
    first, second = phases
    assert _setting(first, 1, "clean_mode") == "vacuum"
    assert _setting(first, 1, "clean_passes") == 2
    assert _setting(second, 1, "clean_mode") == "mop"
    assert _setting(second, 1, "clean_passes") == 1


async def test_qrg_4_three_groups_stay_three_in_order(hass, manager, monkeypatch):
    """[QRG-4] Order is the user's, not the optimiser's — "room A and room B" today,
    "room A and room C" tomorrow, as authored."""
    phases = _phases(manager, monkeypatch, [_rg(1), _rg(2), _rg(3)], included={1, 2, 3})

    assert [p["ids"] for p in phases] == [[1], [2], [3]]


@pytest.mark.parametrize(
    "steps,sequenced",
    [
        ([_rg(1)], False),
        ([_rg(1), _rg(2)], True),
        ([_rg(1), {"type": "charge_wait", "target_battery_percent": 80}], True),
        ([{"type": "zone", "zone_ids": ["z"]}], True),
        ([], False),
    ],
)
async def test_qrg_5_one_question_one_answer(hass, manager, steps, sequenced):
    """[QRG-5] THE DISAGREEMENT THAT CAUSED THE BUG, pinned.

    `has_stops` told the card a multi-group plan was sequenced; the executing gates
    asked a narrower question and said no. Both now call `plan_is_sequenced`, and the
    narrower helper keeps its old meaning for callers that genuinely want "does this
    contain a break" — which is why both are asserted here.
    """
    assert plan_is_sequenced(steps) is sequenced

    # The narrower question is unchanged: shape alone does not make it "stepped".
    if len([s for s in steps if s.get("type") == "room_group"]) > 1 and not any(
        s.get("type") in ("charge_wait", "wait", "zone") for s in steps
    ):
        assert plan_requires_stepped_execution(steps) is False, (
            "the shape clause leaked into the step-type vocabulary"
        )


async def test_qrg_6_a_single_surviving_group_keeps_its_own_settings(hass, manager, monkeypatch):
    """[QRG-6] THE SAME DEFECT AT N=1, found by ablating QRG-2.

    Disabling the collapse changed nothing for one group, which looked like the test
    was weak — and the real answer was that the collapse was doing something worse than
    nothing. It rebuilt the phase with `managed_rooms=effective_rooms`, the GLOBAL view,
    discarding the per-group overlay the builder had just merged and re-protected.

    It is reachable: one room group plus a zone that resolves to nothing drops the zone
    and lands exactly in that branch, so a user whose saved zone went missing silently
    lost that group's settings too. A surviving group is now kept, not rebuilt.
    """
    steps = [
        _rg(1, clean_mode="mop", clean_passes=2),
        {"type": "zone", "zone_ids": ["z_missing"]},
    ]
    # The resolver lives on the MANAGER, not run_plan — same target the zone suite uses.
    monkeypatch.setattr(manager, "_resolve_saved_zone_rects", lambda **kw: [])

    phases = _phases(manager, monkeypatch, steps, included={1})

    assert [p["ids"] for p in phases] == [[1]]
    assert _setting(phases[0], 1, "clean_mode") == "mop", (
        "the surviving group was rebuilt from the global view, losing its settings"
    )
    assert _setting(phases[0], 1, "clean_passes") == 2
