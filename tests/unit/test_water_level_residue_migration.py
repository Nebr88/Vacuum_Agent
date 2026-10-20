"""Carrying a stored water level onto the device's own ladder (issue #71).

The Roborock water vocabulary is now READ off ``select.<obj>_mop_intensity`` rather
than transcribed from one S6. On a Saros 10 the rungs are
``off/mild/standard/intense/extreme``, so a room stored ``water_level: "medium"`` —
written under the old declared ladder — is suddenly out of vocabulary.

THE WHOLE DANGER IS THE OBVIOUS REPAIR. ``vocabulary_migration`` resets an
out-of-vocabulary value to the brand's ``default_profile``, and Roborock's default
profile is ``vacuum_quick``, whose ``water_level`` is ``"off"``. So the obvious repair
turns every room somebody set to medium or high into a room that does not mop — a valid
stored value, a clean migration log, no error anywhere, and a floor that never gets
washed again. It is the same species as the ``fan_speed: "Max" -> "balanced"`` collateral
that made the path_type repair a narrow one, except worse: that one cleaned less, this
one stops cleaning.

``_alias_target`` is consulted BEFORE the default for exactly this case, and the brand
supplies the map positionally — index 2 of the old ladder becomes index 2 of the new
one, because position IS the meaning on an ascending ladder. WLR-1 and WLR-2 are the
pair that proves the alias is load-bearing: one asserts the intent survives, the other
asserts what happens without it, so a future change that drops the alias cannot pass by
quietly producing "off".

Coverage targets
----------------
[WLR-1]  the live case: ``medium`` becomes the device's middle rung, not ``off``.
[WLR-2]  **the alias is load-bearing** — strip it and the same room goes to ``off``.
[WLR-3]  a value the device still has is left alone.
[WLR-4]  its own key: a spent ``room_vocabulary_v1`` does not skip this.
[WLR-5]  and a spent path_type key does not skip it either — the two are independent.
[WLR-6]  idempotent.
[WLR-7]  NARROWING: only ``water_level`` moves; path_type and fan_speed are untouched.
[WLR-8]  an unjudgeable target defers without burning the key.
[WLR-9]  positional mapping, derived: every retired rung maps to its own index.
[WLR-10] a SHORTER device ladder clamps down, never up — under-mop over wet-mop.
[WLR-11] identical ladders declare no aliases at all, so the S6 is inert.
"""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.eufy_vacuum.adapters.roborock.vocabulary import (
    PATH_TYPE_OPTIONS as _RB_PATH_TYPES,
    ROOM_PROFILES as _RB_BUILTINS,
    WATER_LEVEL_OPTIONS as _RB_WATER,
    build_option_list,
    build_positional_aliases,
)
from custom_components.eufy_vacuum.rooms.vocabulary_migration import (
    MIGRATION_KEY,
    RESIDUE_MIGRATION_KEY,
    WATER_RESIDUE_MIGRATION_KEY,
    migrate_water_level_residue,
)

from tests.brand_catalogs import ROBOROCK_BLOCK

_VAC = "vacuum.saros"

#: Pasted unmodified from the reporter's Developer Tools, issue #71 (2026-10-19).
SAROS_LADDER = ["off", "mild", "standard", "intense", "extreme", "smart_mode", "custom"]

_DECLARED = [str(o["value"]) for o in _RB_WATER]
_DEFAULT_WATER = _RB_BUILTINS[ROBOROCK_BLOCK["default_profile"]]["water_level"]


def _vocabulary(ladder=SAROS_LADDER, *, aliases=True) -> dict[str, Any]:
    """The vocabulary block the adapter assembles for a device publishing ``ladder``."""
    options = build_option_list(ladder)
    block: dict[str, Any] = {
        "water_level_options": options,
        "path_type_options": _RB_PATH_TYPES,
    }
    if aliases:
        derived = build_positional_aliases(_DECLARED, [o["value"] for o in options])
        if derived:
            block["water_level_aliases"] = derived
    return block


def _config(**overrides: Any) -> dict[str, Any]:
    config = {
        "adapter_id": "roborock",
        "room_profiles": ROBOROCK_BLOCK,
        "vocabulary": _vocabulary(),
    }
    config.update(overrides)
    return config


def _getter(config, vacuum: str = _VAC):
    return lambda vacuum_entity_id: config if vacuum_entity_id == vacuum else None


def _data(rooms: dict, vacuum: str = _VAC) -> dict:
    return {"maps": {vacuum: {"1": {"rooms": rooms}}}}


def _room(**fields: Any) -> dict:
    base = {"room_id": 3, "name": "Kitchen", "map_id": "1"}
    base.update(fields)
    return base


def _water_of(data, room="3"):
    return data["maps"][_VAC]["1"]["rooms"][room]["water_level"]


# ---------------------------------------------------------------------------
# The pair that proves the alias is load-bearing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "stored,expected",
    [("low", "mild"), ("medium", "standard"), ("high", "intense")],
)
def test_wlr_1_a_retired_rung_keeps_its_position(stored, expected):
    """[WLR-1] The live case. Index 2 of the old ladder becomes index 2 of the new one.

    Parameterized across all three retired rungs rather than written for ``medium``
    alone: a mapping that happened to be right for the middle and wrong at the ends
    would pass a single-value test and quietly mis-set two thirds of a user's rooms.
    """
    data = _data({"3": _room(water_level=stored)})

    migrate_water_level_residue(data=data, get_config=_getter(_config()))

    assert _water_of(data) == expected
    assert expected != _DEFAULT_WATER, "this assertion is worthless if the two agree"


def test_wlr_2_without_the_alias_the_same_room_stops_mopping():
    """[WLR-2] WHAT THE ALIAS IS PROTECTING AGAINST, asserted directly.

    Same room, same device, same repair — only the brand's alias declaration removed.
    The planner then falls through to ``default_profile``, which for Roborock is
    ``vacuum_quick`` (``water_level: "off"``). A room somebody set to the middle rung
    becomes a room that does not mop.

    This is deliberately an assertion about the BAD outcome. WLR-1 alone would stay
    green if a future change made aliases optional-but-absent and the default happened
    to look reasonable; this one names the failure so dropping the alias is loud.
    """
    data = _data({"3": _room(water_level="medium")})
    no_aliases = _config(vocabulary=_vocabulary(aliases=False))

    migrate_water_level_residue(data=data, get_config=_getter(no_aliases))

    assert _water_of(data) == _DEFAULT_WATER == "off"


def test_wlr_3_a_rung_the_device_still_has_is_left_alone():
    """[WLR-3] ``off`` survives both ladders, so nothing is retired about it."""
    data = _data({"3": _room(water_level="off")})

    result = migrate_water_level_residue(data=data, get_config=_getter(_config()))

    assert result["changes"] == []
    assert _water_of(data) == "off"


# ---------------------------------------------------------------------------
# Independence and narrowing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("spent", [MIGRATION_KEY, RESIDUE_MIGRATION_KEY])
def test_wlr_4_5_a_spent_sibling_key_does_not_skip_this_repair(spent):
    """[WLR-4][WLR-5] Every install that predates this carries BOTH sibling keys
    latched. Sharing either would skip exactly the installs that need repairing."""
    data = _data({"3": _room(water_level="medium")})
    data["migrations"] = {spent: True}

    result = migrate_water_level_residue(data=data, get_config=_getter(_config()))

    assert result["ran"] is True
    assert _water_of(data) == "standard"
    assert data["migrations"][spent] is True  # not disturbed
    assert data["migrations"][WATER_RESIDUE_MIGRATION_KEY] is True


def test_wlr_6_idempotent():
    """[WLR-6] The second run neither re-plans nor re-writes."""
    data = _data({"3": _room(water_level="medium")})
    get_config = _getter(_config())

    assert migrate_water_level_residue(data=data, get_config=get_config)["ran"] is True
    data["maps"][_VAC]["1"]["rooms"]["3"]["water_level"] = "extreme"

    again = migrate_water_level_residue(data=data, get_config=get_config)

    assert again == {"ran": False, "changes": [], "rooms_touched": 0}
    assert _water_of(data) == "extreme"


def test_wlr_7_only_the_water_axis_moves():
    """[WLR-7] The narrowing. ``path_type`` and ``fan_speed`` on the same room are out
    of vocabulary too, and neither is this repair's business."""
    data = _data({"3": _room(water_level="medium", path_type="wide", fan_speed="Max")})

    changes = migrate_water_level_residue(
        data=data, get_config=_getter(_config())
    )["changes"]

    room = data["maps"][_VAC]["1"]["rooms"]["3"]
    assert [c["field"] for c in changes] == ["water_level"]
    assert room["path_type"] == "wide"
    assert room["fan_speed"] == "Max"


def test_wlr_8_an_unjudgeable_target_defers_without_burning_the_key():
    """[WLR-8] The MIG-11 rule, inherited: a vacuum whose adapter has not registered is
    not a verdict of "nothing to do"."""
    data = _data({"3": _room(water_level="medium")})
    data["maps"]["vacuum.later"] = {"1": {"rooms": {"9": _room(room_id=9)}}}

    result = migrate_water_level_residue(data=data, get_config=_getter(_config()))

    assert result["latched"] is False
    assert WATER_RESIDUE_MIGRATION_KEY not in data.get("migrations", {})
    assert _water_of(data) == "standard"


# ---------------------------------------------------------------------------
# The derivation itself
# ---------------------------------------------------------------------------

def test_wlr_9_positional_mapping_is_derived_not_typed():
    """[WLR-9] Asserted against the index rather than a transcript, so the test cannot
    agree with a hand-written table that drifted from the rule."""
    live = ["off", "mild", "standard", "intense", "extreme"]
    aliases = build_positional_aliases(_DECLARED, live)

    for index, declared in enumerate(_DECLARED):
        if declared in live:
            assert declared not in aliases, "a live rung needs no alias"
        else:
            assert aliases[declared] == live[index]


def test_wlr_10_a_shorter_device_ladder_clamps_down_never_up():
    """[WLR-10] A device offering only off/low has no rung for ``high``. Clamping to its
    top is the safe direction for this axis — under-mop is accepted over wet-mop, the
    same asymmetry ``mixed_mode_water_policy: "safest"`` rests on. Leaving it unmapped
    would send it to the default, which is ``off``."""
    aliases = build_positional_aliases(_DECLARED, ["off", "low"])

    assert aliases == {"medium": "low", "high": "low"}


def test_wlr_11_an_unchanged_ladder_declares_no_aliases():
    """[WLR-11] The S6 case, and why this is inert on a machine whose vocabulary did not
    move: every declared word is still live, so nothing is retired."""
    assert build_positional_aliases(_DECLARED, _DECLARED) == {}
    assert "water_level_aliases" not in _vocabulary(_DECLARED)


def test_wlr_12_a_fallback_vocabulary_defers_instead_of_burning_the_key():
    """[WLR-12] THE DEFECT THE PRE-RELEASE AUDIT CAUGHT, and it made this whole repair
    a no-op on the install it was written for.

    Adapters read their option lists off the provider's entities, and at the start hook
    this repair runs from, the provider's coordinator may not have polled. The adapter
    then falls back to its DECLARED list and says so, by naming the entities it could
    not read (``_pending_live_reads``).

    Judged against that fallback — Roborock's declared ``off/low/medium/high`` — a Saros
    10's stored ``medium`` looks perfectly in-vocabulary. Nothing is planned, and the
    ONE-SHOT key latches having repaired nothing. The real ladder is
    ``off/mild/standard/intense/extreme``, so the room keeps a value the device rejects,
    and ``dispatch/manager.py`` then finds nothing rankable and skips the safest-water
    pre-call entirely — issue #51's wet-mop, with no error anywhere.

    The latch condition must therefore treat "this vocabulary is a guess" as
    unadjudicated, exactly as it already treats "this adapter declared nothing".
    """
    data = _data({"3": _room(water_level="medium")})
    fallback = _config(
        vocabulary={"water_level_options": _RB_WATER},   # the DECLARED ladder
        _pending_live_reads=["select.saros_mop_intensity"],
    )

    result = migrate_water_level_residue(data=data, get_config=_getter(fallback))

    assert result["latched"] is False, (
        "latched against a vocabulary the adapter had just declared to be a fallback"
    )
    assert WATER_RESIDUE_MIGRATION_KEY not in data.get("migrations", {})
    assert _water_of(data) == "medium", "nothing should be rewritten from a guess"


def test_wlr_13_the_same_room_repairs_once_the_real_ladder_arrives():
    """[WLR-13] The other arm: deferring is only correct if the work later happens.

    Without this, WLR-12 is satisfied by a repair that defers forever.
    """
    data = _data({"3": _room(water_level="medium")})
    live = _config()  # the Saros ladder, nothing pending

    result = migrate_water_level_residue(data=data, get_config=_getter(live))

    assert result["latched"] is True
    assert _water_of(data) == "standard"
