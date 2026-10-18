"""The NARROW repair: one axis whose option list changed after the broad latch.

v2.2.4 replaced Roborock's ``path_type`` options ``wide``/``narrow`` with
``standard``/``deep``/``deep_plus`` and bumped no migration key. ``room_vocabulary_v1``
had already latched on every install that existed before that release, so the value it
was supposed to repair is still on disk: measured on this house's box, twelve of
``vacuum.ivy``'s rooms carry ``path_type: "wide"`` with ``room_vocabulary_v1: True``
beside them.

WHAT THESE TESTS ARE REALLY GUARDING is not that ``wide`` becomes ``standard`` — that
is one line and hard to get wrong. It is everything the repair must NOT do. Both
planners were dry-run over that same stored data: this repair plans 12 changes, all of
them the intended resets; re-opening the broad one plans 13, the extra being
``fan_speed: "Max"`` falling to the default profile's ``balanced`` on one room — the
fastest suction quietly moved to the middle, no alias to carry the intent, no error to
notice. PTR-3 is the test that fails if that narrowing is ever lost.

Fixtures come from the Roborock adapter's own constants by reference, never copied: a
hand-written option list would let this suite keep passing after the real one changes
again, which is the exact failure being repaired.

Coverage targets
----------------
[PTR-1] the live case: a retired ``wide`` becomes the brand's default_profile value.
[PTR-2] ``narrow``, the other retired value, is repaired by the same rule — not by a
        hardcoded knowledge of the string ``wide``.
[PTR-3] NARROWING: out-of-vocabulary ``clean_mode`` and ``fan_speed`` in the same room
        are left exactly alone. This is the collateral the broad repair would cause.
[PTR-4] an in-vocabulary ``path_type`` is not touched.
[PTR-5] RESETS ONLY — an Eufy room's ``path_type``, which the broad repair DROPS,
        is left alone here.
[PTR-6] its own key: a spent ``room_vocabulary_v1`` does not skip this repair.
[PTR-7] idempotent, and the second run reports it did not run.
[PTR-8] a target with stored rooms and no declaration DEFERS; the key is not burned.
[PTR-9] ``fields`` is an intersection with the vocabulary axes, not a replacement —
        a caller cannot get ``name`` judged.
[PTR-10] no declared ``path_type_options`` means "cannot judge", never "reset it".
[PTR-11] every axis named in ``RESIDUE_FIELDS`` is a real vocabulary axis — a rename
         would otherwise narrow the repair to nothing, silently.
"""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.eufy_vacuum.adapters.roborock.vocabulary import (
    CLEAN_MODE_OPTIONS as _RB_CLEAN_MODES,
    FAN_SPEED_OPTIONS as _RB_FAN_SPEEDS,
    PATH_TYPE_OPTIONS as _RB_PATH_TYPES,
    ROOM_PROFILES as _RB_BUILTINS,
    WATER_LEVEL_OPTIONS as _RB_WATER_LEVELS,
)
from custom_components.eufy_vacuum.profiles.room_profiles import VOCABULARY_FIELDS
from custom_components.eufy_vacuum.rooms.vocabulary_migration import (
    MIGRATION_KEY,
    RESIDUE_FIELDS,
    RESIDUE_MIGRATION_KEY,
    migrate_path_type_residue,
    plan_path_type_residue_repair,
    plan_room_vocabulary_migration,
)

from tests.brand_catalogs import EUFY_BLOCK, ROBOROCK_BLOCK

_VAC = "vacuum.ivy"

#: What the brand's own default profile answers for this axis. Derived, never typed:
#: the assertion must track the adapter, not a transcript of it.
_DEFAULT_PATH_TYPE = _RB_BUILTINS[ROBOROCK_BLOCK["default_profile"]]["path_type"]


def _rb_vocabulary(**overrides: Any) -> dict[str, Any]:
    """The Roborock vocabulary block as ``adapter.py`` assembles it for a settable mop.

    clean_mode and water_level ride only on a mop-settable model; both are included
    here deliberately, because PTR-3's whole point is that a JUDGEABLE out-of-vocabulary
    value on another axis is still not judged.
    """
    vocabulary = {
        "fan_speed_options": _RB_FAN_SPEEDS,
        "path_type_options": _RB_PATH_TYPES,
        "clean_mode_options": _RB_CLEAN_MODES,
        "water_level_options": _RB_WATER_LEVELS,
    }
    vocabulary.update(overrides)
    return vocabulary


def _config(**overrides: Any) -> dict[str, Any]:
    config = {
        "adapter_id": "roborock",
        "room_profiles": ROBOROCK_BLOCK,
        "vocabulary": _rb_vocabulary(),
    }
    config.update(overrides)
    return config


def _getter(config, vacuum: str = _VAC):
    return lambda vacuum_entity_id: config if vacuum_entity_id == vacuum else None


def _data(rooms: dict, vacuum: str = _VAC) -> dict:
    return {"maps": {vacuum: {"1": {"rooms": rooms}}}}


def _room(**fields: Any) -> dict:
    base = {"room_id": 16, "name": "Kitchen", "map_id": "1"}
    base.update(fields)
    return base


# ---------------------------------------------------------------------------
# The repair itself
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("retired", ["wide", "narrow"])
def test_ptr_1_2_a_retired_path_type_becomes_the_brands_default(retired):
    """[PTR-1][PTR-2] Both values v2.2.4 retired are repaired, by the same rule.

    Parameterized rather than written twice because a repair that knows the string
    ``wide`` would pass the live case and leave ``narrow`` — which the same release
    retired — on disk forever.
    """
    data = _data({"16": _room(path_type=retired)})

    result = migrate_path_type_residue(data=data, get_config=_getter(_config()))

    assert result["ran"] is True
    assert result["rooms_touched"] == 1
    assert data["maps"][_VAC]["1"]["rooms"]["16"]["path_type"] == _DEFAULT_PATH_TYPE
    assert _DEFAULT_PATH_TYPE in {o["value"] for o in _RB_PATH_TYPES}


def test_ptr_3_other_out_of_vocabulary_axes_are_left_exactly_alone():
    """[PTR-3] The narrowing, and the reason this repair exists as its own key.

    This room is ivy's real shape: a retired ``path_type`` sitting beside a
    ``clean_mode`` and a ``fan_speed`` that are ALSO out of vocabulary (the stored
    values are display-cased, the declared ones are codes). Re-opening the broad repair
    would rewrite all three; ``fan_speed`` in particular would fall to the default
    profile's value, moving a room from the fastest suction to the middle.

    Remove the ``fields`` filter and this goes red.
    """
    data = _data({"16": _room(path_type="wide", clean_mode="Vacuum", fan_speed="Max")})

    changes = migrate_path_type_residue(
        data=data, get_config=_getter(_config())
    )["changes"]

    room = data["maps"][_VAC]["1"]["rooms"]["16"]
    assert room["path_type"] == _DEFAULT_PATH_TYPE
    assert room["clean_mode"] == "Vacuum"
    assert room["fan_speed"] == "Max"
    assert [c["field"] for c in changes] == ["path_type"]

    # And the collateral is real, not hypothetical: the BROAD planner, run over the
    # same room, plans both of the others. Without this the assertions above could
    # pass because nothing was out of vocabulary rather than because the filter held.
    broad = plan_room_vocabulary_migration(data=data, get_config=_getter(_config()))
    assert {c["field"] for c in broad} == {"clean_mode", "fan_speed"}


def test_ptr_4_an_in_vocabulary_path_type_is_untouched():
    """[PTR-4] A value the user may have chosen is not re-adjudicated."""
    declared = _RB_PATH_TYPES[-1]["value"]
    assert declared != _DEFAULT_PATH_TYPE  # or the assertion below proves nothing
    data = _data({"16": _room(path_type=declared)})

    result = migrate_path_type_residue(data=data, get_config=_getter(_config()))

    assert result["changes"] == []
    assert data["maps"][_VAC]["1"]["rooms"]["16"]["path_type"] == declared


def test_ptr_5_resets_only_never_drops():
    """[PTR-5] RESETS ONLY, on the shape that actually reaches it: an EUFY room
    carrying ``path_type``.

    Eufy declares the axis in no profile — it is a deliberate subtraction, the second
    name for what Eufy calls ``clean_intensity`` — so this same field on this brand is
    a DROP, not a reset. The narrow repair must leave it: a DROP answers "does this
    brand have the axis at all?", which is the broad repair's question, settled under
    the broad repair's latch. Re-asking it through a smaller door is the collateral
    this key exists to avoid, and dropping a field is the more destructive of the two
    answers to get wrong. The room self-heals anyway — ``_finalize_room_update`` strips
    an undeclared field on the next save.

    No vocabulary is declared here, deliberately: a DROP is decided by the PROFILES
    before any option list is consulted, which is the module's own safety rule.
    """
    data = _data({"16": _room(path_type="wide")})
    config = _config(adapter_id="eufy", room_profiles=EUFY_BLOCK, vocabulary={})

    changes = migrate_path_type_residue(data=data, get_config=_getter(config))["changes"]

    assert changes == []
    assert data["maps"][_VAC]["1"]["rooms"]["16"]["path_type"] == "wide"

    # The drop is real and reachable — the broad planner, same room, same config,
    # plans it. Without this the assertions above could pass because nothing was
    # planned at all.
    broad = plan_room_vocabulary_migration(data=data, get_config=_getter(config))
    assert [(c["field"], c["action"]) for c in broad] == [("path_type", "drop")]


def test_ptr_6_runs_even_though_the_broad_repair_already_latched():
    """[PTR-6] The upgrader's real state, and the entire reason for a second key.

    Every install that predates v2.2.4 has ``room_vocabulary_v1: True`` on disk. If
    this repair shared that key it would be skipped on exactly the installs that need
    it, and pass every test written on a fresh dict.
    """
    data = _data({"16": _room(path_type="wide")})
    data["migrations"] = {MIGRATION_KEY: True}

    result = migrate_path_type_residue(data=data, get_config=_getter(_config()))

    assert result["ran"] is True
    assert data["maps"][_VAC]["1"]["rooms"]["16"]["path_type"] == _DEFAULT_PATH_TYPE
    assert data["migrations"][MIGRATION_KEY] is True  # not disturbed
    assert data["migrations"][RESIDUE_MIGRATION_KEY] is True


def test_ptr_7_runs_once_and_a_later_edit_stays():
    """[PTR-7] Idempotent. A second run neither re-plans nor re-writes."""
    data = _data({"16": _room(path_type="wide")})
    get_config = _getter(_config())

    assert migrate_path_type_residue(data=data, get_config=get_config)["ran"] is True

    chosen = _RB_PATH_TYPES[-1]["value"]
    data["maps"][_VAC]["1"]["rooms"]["16"]["path_type"] = chosen
    again = migrate_path_type_residue(data=data, get_config=get_config)

    assert again == {"ran": False, "changes": [], "rooms_touched": 0}
    assert data["maps"][_VAC]["1"]["rooms"]["16"]["path_type"] == chosen


def test_ptr_8_an_unjudgeable_target_defers_without_burning_the_key():
    """[PTR-8] A vacuum with stored rooms whose adapter has not registered is not a
    verdict of "nothing to do" — the run is retried on the next start."""
    data = _data({"16": _room(path_type="wide")})
    data["maps"]["vacuum.later"] = {"1": {"rooms": {"2": _room(room_id=2)}}}

    result = migrate_path_type_residue(data=data, get_config=_getter(_config()))

    assert result["latched"] is False
    assert RESIDUE_MIGRATION_KEY not in data.get("migrations", {})
    # The vacuum it COULD judge is still repaired; deferral is about the latch.
    assert data["maps"][_VAC]["1"]["rooms"]["16"]["path_type"] == _DEFAULT_PATH_TYPE


# ---------------------------------------------------------------------------
# The planner's new filter
# ---------------------------------------------------------------------------

def test_ptr_9_fields_cannot_name_something_that_is_not_a_vocabulary_axis():
    """[PTR-9] ``fields`` intersects the vocabulary axes; it does not replace them.

    ``name`` and ``room_id`` live in the same dict as the settings. A filter written as
    ``for field in (fields or _VOCABULARY_FIELDS)`` would judge them — and ``name`` is
    in no option list, so every room would be stripped of its name.
    """
    data = _data({"16": _room(path_type="wide")})

    planned = plan_room_vocabulary_migration(
        data=data, get_config=_getter(_config()), fields=("name", "room_id"),
    )

    assert planned == []
    assert data["maps"][_VAC]["1"]["rooms"]["16"]["name"] == "Kitchen"


def test_ptr_10_no_declared_option_list_means_cannot_judge():
    """[PTR-10] The S6 safety rule, which this repair inherits unchanged: a brand that
    declares no option list for the axis is not judged against an empty set."""
    vocabulary = _rb_vocabulary()
    vocabulary.pop("path_type_options")
    data = _data({"16": _room(path_type="wide")})

    planned = plan_path_type_residue_repair(
        data=data, get_config=_getter(_config(vocabulary=vocabulary)),
    )

    assert planned == []
    assert data["maps"][_VAC]["1"]["rooms"]["16"]["path_type"] == "wide"


def test_ptr_11_every_residue_field_is_a_real_vocabulary_axis():
    """[PTR-11] ``RESIDUE_FIELDS`` is intersected with ``VOCABULARY_FIELDS``, so a name
    that is not an axis narrows the repair to NOTHING — no error, no log, no changes,
    and the residue stays on disk under a key that has latched. The failure mode of a
    filter is silence, which is why it needs a test of its own rather than a comment.
    """
    assert set(RESIDUE_FIELDS) <= set(VOCABULARY_FIELDS)
