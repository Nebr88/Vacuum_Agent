"""One physical axis, more than one brand name (issue #71).

Eufy and Dreame declare the pass-density axis as `clean_intensity`. Roborock declares
the SAME physical property as `path_type` — a name this project invented in its initial
release, three weeks before adapters or a second brand existed, as a duplicate of an
axis already carried (`docs/dev/24-roborock-adapter.md` §8). Every card surface reads
`clean_intensity_options`; `path_type_options` appears ZERO times in `src/`. So the
picker has never rendered for that brand, on any install, since the axis was added.

THE FIX IS A RESOLUTION, NOT A SECOND KEY IN THE CARD. The canonical name stays the
card's whole interface and the brand's own field is resolved server-side, so a third
brand with a third word costs one tuple entry and no card change. These tests pin the
properties that make that safe to expand.

Coverage targets
----------------
[AX-1] a brand declaring the canonical key resolves to it — Eufy/Dreame unchanged.
[AX-2] a brand declaring only its own name resolves to THAT field — the Roborock case.
[AX-3] the canonical name wins when a brand somehow declares both, so the duplicate
       can be retired later by deleting a profile copy and nothing else.
[AX-4] a brand declaring neither gets the canonical field and NO options — "cannot
       offer", which is not the same statement as "has no such axis".
[AX-5] an empty or malformed list is not a declaration.
[AX-6] an unknown axis name resolves to itself, so the helper is safe to call for any
       field rather than only the ones in the table.
[AX-7] **every candidate field is a real vocabulary field** — a typo in the table would
       silently resolve to a key nothing writes.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.roborock.vocabulary import (
    PATH_TYPE_OPTIONS as _RB_PATH_TYPES,
)
from tests.brand_catalogs import EUFY_BLOCK, ROBOROCK_BLOCK

from custom_components.eufy_vacuum.profiles.room_profiles import (
    AXIS_FIELD_CANDIDATES,
    VOCABULARY_FIELDS,
    default_setting_values,
    resolve_axis,
)

_EUFY_INTENSITY = [
    {"value": "Quick", "label": "Quick"},
    {"value": "Narrow", "label": "Narrow"},
    {"value": "Deep", "label": "Deep"},
]


def test_ax_1_the_canonical_key_resolves_to_itself():
    """[AX-1] Eufy and Dreame declare `clean_intensity_options`; nothing about them
    changes, which is what makes this safe to land for one brand."""
    field, options = resolve_axis(
        {"clean_intensity_options": _EUFY_INTENSITY}, "clean_intensity"
    )

    assert field == "clean_intensity"
    assert options == _EUFY_INTENSITY


def test_ax_2_a_brands_own_name_resolves_to_that_field():
    """[AX-2] THE LIVE CASE. Roborock declares only `path_type_options`, so the card
    gets the list under the canonical name and is told to WRITE `path_type`.

    The returned FIELD is the load-bearing half. Returning the options alone would
    render a picker that saves to `clean_intensity` — a field absent from every
    Roborock profile, which `_finalize_room_update` strips on the next save. That is
    the trap the obvious one-line version of this fix falls into.
    """
    field, options = resolve_axis(
        {"path_type_options": _RB_PATH_TYPES}, "clean_intensity"
    )

    assert field == "path_type"
    assert options == _RB_PATH_TYPES


def test_ax_3_the_canonical_name_wins_when_both_are_declared():
    """[AX-3] The retirement path. A brand that declares both gets the canonical one,
    so `path_type` can later be dropped by deleting its copy from the profiles — with
    no change to this table, the card, or the resolver."""
    field, options = resolve_axis(
        {
            "clean_intensity_options": _EUFY_INTENSITY,
            "path_type_options": _RB_PATH_TYPES,
        },
        "clean_intensity",
    )

    assert field == "clean_intensity"
    assert options == _EUFY_INTENSITY


@pytest.mark.parametrize(
    "vocabulary",
    [
        {},
        None,
        {"clean_intensity_options": []},
        {"path_type_options": []},
        {"clean_intensity_options": "not a list"},
        {"clean_intensity_options": None},
    ],
)
def test_ax_4_5_no_declaration_yields_the_canonical_field_and_no_options(vocabulary):
    """[AX-4][AX-5] "Cannot offer this axis" — the card renders no picker, exactly as
    today. Deliberately NOT the same statement as "this brand has no such axis", which
    is `declared_profile_fields`' question and the one that licenses DROPPING a stored
    value. Conflating them is what nearly stripped `clean_mode` and `water_level` from
    every S6 room (MIG-5).

    An empty or malformed list is not a declaration, so it cannot resolve the field
    away from the canonical name.
    """
    field, options = resolve_axis(vocabulary, "clean_intensity")

    assert field == "clean_intensity"
    assert options == []


def test_ax_6_an_unlisted_axis_resolves_to_itself():
    """[AX-6] The helper is total: calling it for an axis with no alias row behaves
    exactly like reading `<axis>_options` directly, so a caller never has to ask
    whether a given field is in the table before using it."""
    field, options = resolve_axis({"fan_speed_options": [{"value": "max"}]}, "fan_speed")

    assert field == "fan_speed"
    assert options == [{"value": "max"}]

    field, options = resolve_axis({}, "fan_speed")
    assert (field, options) == ("fan_speed", [])


def test_ax_7_every_candidate_is_a_real_vocabulary_field():
    """[AX-7] A typo in the table resolves to a key nothing writes, and the symptom is
    a picker that silently saves nothing — the same class as the defect being fixed.

    Asserted against `VOCABULARY_FIELDS` rather than a transcript, so adding a brand
    word to the table without adding it to the framework's own axis list goes red here
    instead of in a user's room.
    """
    for axis, candidates in AXIS_FIELD_CANDIDATES.items():
        assert axis in VOCABULARY_FIELDS, f"{axis} is not a vocabulary field"
        assert candidates[0] == axis, (
            f"{axis}: the canonical name must come first, or AX-3's retirement path "
            "resolves to the brand word forever"
        )
        for candidate in candidates:
            assert candidate in VOCABULARY_FIELDS, (
                f"{axis} -> {candidate!r} is not a vocabulary field"
            )


def test_ax_8_the_fold_survives_a_caller_that_already_resolved_the_axis():
    """[AX-8] ORDER IS LOAD-BEARING, and the obvious order silently defeats the fold.

    `default_setting_values` folds a brand's own pass-density field onto the canonical
    name by asking `resolve_axis` which field this brand uses. A caller that has ALREADY
    inserted the canonical key into the vocabulary it then passes here gets a resolver
    answer of "clean_intensity" — the key the caller just wrote — so the fold never
    runs and the result carries `path_type`, which no consumer reads.

    That shipped: `core/manager.py` built the snapshot's vocabulary copy, inserted
    `clean_intensity_options` into it, and derived the defaults from that same copy. The
    card then could not tell a Roborock room was at its default, so the path chip
    rendered on EVERY room — the exact opposite of the change's purpose, on the one
    brand it was written for, with every test green.

    The left column is the brand's own declaration; the right is a caller that resolved
    first. Both must produce the canonical key.
    """
    brand_declared = {"path_type_options": _RB_PATH_TYPES}
    already_resolved = {
        "path_type_options": _RB_PATH_TYPES,
        "clean_intensity_options": _RB_PATH_TYPES,
    }

    for vocabulary, label in ((brand_declared, "as declared"),
                              (already_resolved, "caller resolved first")):
        defaults = default_setting_values(ROBOROCK_BLOCK, vocabulary)
        assert "clean_intensity" in defaults, f"{label}: the fold did not run"
        assert "path_type" not in defaults, (
            f"{label}: left the brand's own field name, which nothing reads"
        )
        assert defaults["clean_intensity"] == _RB_DEFAULT_PATH


def test_ax_9_a_canonical_brand_is_unaffected_by_the_fold():
    """[AX-9] Eufy and Dreame name the axis canonically, so there is nothing to fold —
    and the fold must not disturb them. Without this, AX-8 could be satisfied by always
    renaming something."""
    defaults = default_setting_values(
        EUFY_BLOCK, {"clean_intensity_options": _EUFY_INTENSITY}
    )
    assert defaults["clean_intensity"] == EUFY_BLOCK["builtins"][EUFY_BLOCK["default_profile"]]["clean_intensity"]
    assert "path_type" not in defaults


_RB_DEFAULT_PATH = ROBOROCK_BLOCK["builtins"][ROBOROCK_BLOCK["default_profile"]]["path_type"]
