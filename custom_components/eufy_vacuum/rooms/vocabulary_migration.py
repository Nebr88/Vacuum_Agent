"""One-shot repair of room settings written under the framework's old Eufy default.

Until 2026-08-07 ``resolve_profile_catalog`` returned Eufy's catalog when an adapter
declared none, and several room-writing paths never consulted an adapter at all. Every
room those paths touched — on ANY brand — was written with Eufy's vocabulary. Removing
the fallback stops new rooms being born that way; it cannot heal rooms already on disk,
because a stored per-room field wins over the profile it claims. This is the healing
half, and it runs once.

Two rules, both driven by what the brand DECLARES. Neither infers anything from a value's
shape, and neither has brand knowledge of its own:

**DROP** — the room carries a field that appears in NO profile the brand declares
(neither its ``builtins`` nor its ``custom_template``). The brand has no such axis, so
the stored value came from somewhere else. Roborock is the live case: it omits
``clean_intensity`` from every profile on purpose (``roborock/vocabulary.py``), yet
Roborock rooms carry it.

**RESET** — the brand declares an option list for the field and the stored value is not
in it. A retired value the brand still declares an ALIAS for keeps its meaning
(``standard`` -> ``narrow``); only a value with no alias falls back to the default. The value cannot be selected in the card and is filtered out before dispatch
(``jobs/active_job.py`` skips a ``per_room_live_settings`` entry whose value is outside
its ``options_key``), so the setting silently does nothing. It becomes the brand's
``default_profile`` value for that field — a declared, in-vocabulary answer.

RESET deliberately does NOT pick a "nearest" option. There is no ordering to be nearest
in — the option lists are declared sets, not scales — and inventing one would be the same
class of guess as the default that caused this.

What this replaces
------------------
``normalize_clean_intensity`` folded the retired Eufy values ``standard``/``normal`` to
``"Quick"`` on every read, forever, from nine call sites. It is subsumed here without a
retired-value map: ``Standard`` is absent from Eufy's declared
``clean_intensity_options``, so RESET catches it, and Eufy's declared
``clean_intensity_aliases`` (``standard`` -> ``narrow``) then supplies the answer.

NOT the identical result, and deliberately so. The old fold produced ``"Quick"``, the
FASTEST density. ``Standard`` was the MIDDLE one — the original YAML system declared
Fast / Standard / Deep with Standard as the initial value, and upstream still maps
``standard`` to ``CleanExtent.NORMAL`` (0), the middle. Folding it to Quick silently
moved every affected room to a different density. The alias is what preserves the
meaning; the default-profile fallback is only for a retired value the brand declares no
alias for. Persisting the result is what lets the read-time fold be deleted.

Safety
------
The rules only ever act on a DECLARATION being present. A brand that declares no options
for a field is not judged — Roborock withholds ``water_level_options`` on models whose mop
is not settable, and treating that absence as "no such axis" would strip ``water_level``
and ``clean_mode`` from every room on an S6. Absence of an option list means "cannot
judge", never "does not exist"; only absence from the brand's own PROFILES means that.
"""

from __future__ import annotations

import logging
from collections.abc import Collection
from typing import Any

from ..profiles.room_profiles import VOCABULARY_FIELDS, declared_profile_fields

_LOGGER = logging.getLogger(__name__)

#: Bumping this re-runs the migration for every install. Only do that if the rules
#: themselves change in a way that must be re-applied — the flag exists so a repaired
#: room is not repaired again after the user deliberately edits it back.
MIGRATION_KEY = "room_vocabulary_v1"

#: Shared with ``ProfileManager._finalize_room_update`` — the repair and the save path
#: must agree on which axes a brand has, or the repair undoes itself one room at a time.
_VOCABULARY_FIELDS = VOCABULARY_FIELDS


def _option_values(vocabulary: dict[str, Any], field: str) -> set[str] | None:
    """Declared option values for ``field``, or None when the brand declares none.

    None means "cannot judge", and every caller must treat it that way — see the
    module docstring's safety note.
    """
    options = vocabulary.get(f"{field}_options")
    if not isinstance(options, list) or not options:
        return None
    values = {str(o.get("value")) for o in options if isinstance(o, dict) and "value" in o}
    return values or None


def _alias_target(
    vocabulary: dict[str, Any], field: str, value: Any, allowed: set[str]
) -> str | None:
    """The declared option a retired value ALIASES to, or None if it aliases to none.

    Alias tables map a lowercased display string to a canonical lowercase code
    ("standard" -> "narrow"), while the declared options carry the brand's own casing
    ("Narrow"), so the match is case-insensitive. An alias pointing at something the
    brand does not declare is ignored rather than written — that is an adapter defect,
    and honouring it would put an undeliverable value on a room.
    """
    aliases = vocabulary.get(f"{field}_aliases")
    if not isinstance(aliases, dict):
        return None
    target = aliases.get(str(value).strip().lower())
    if target is None:
        return None
    for option in allowed:
        if str(option).strip().lower() == str(target).strip().lower():
            return option
    return None


def _unadjudicated_targets(*, data: dict[str, Any], get_config) -> list[str]:
    """Vacuums that HAVE stored rooms but whose adapter presented no declaration.

    These are targets this repair is responsible for and could not evaluate — as
    distinct from targets it evaluated and found nothing to do for. The planner skips
    both (neither licenses an edit), but only the second means the work is finished.

    ⚠ AN ABSENT BLOCK DOES NOT RELIABLY MEAN "not registered YET", AND THIS DOCSTRING
    CLAIMED IT DID UNTIL 2026-08-24 (R10/C61). It credited
    ``registry._validate_room_profiles`` with REJECTING an adapter whose
    ``room_profiles`` is missing or empty. That function only RETURNS issue strings;
    ``register_adapter_config`` logs them at WARNING and **hard-raises only when
    ``config.get("source") == "config"``**. A CODE-sourced adapter is warn-only and
    registers anyway, so ``get_config`` can return a live config with no
    ``room_profiles`` — exactly the state the old text called impossible. The
    correctly-scoped wording already existed 460 lines away, at
    ``registry._warn_completion_gate_orphan``: "hard-raised for a stored config by the
    caller".

    THE ROUTE THAT ACTUALLY REACHES THIS IS A DIFFERENT ONE, and it is worth stating
    because the obvious reading sends a reader to audit the adapters, where they will
    find nothing. Both shipped adapters declare ``room_profiles`` as unconditional dict
    literals, nothing mutates it afterwards, the config path forces
    ``source="config"``, and there is no third code adapter — so the ADAPTER-DEFECT
    route is not live today. The live one is ``brands.resolve_brand`` returning
    UNSUPPORTED: it registers NOTHING while the vacuum stays managed, so
    ``get_config`` returns ``None`` forever and the vacuum is permanently pending, with
    the WARNING re-emitted on every start. No adapter defect required.

    ⚠ THE DEFERRED-LATCH DESIGN BELOW WAS WRITTEN AGAINST A COLD-BOOT RACE, WHERE
    WAITING WORKS. It has never been reconciled with the unsupported-brand arm, which
    shipped later and makes "not registered yet" permanently false rather than
    temporarily so. THIS TEXT CALLED THAT AN OPEN DESIGN QUESTION UNTIL 2026-08-24; IT
    IS RULED (C61). A target that can never be adjudicated does NOT get a terminal
    disposition — the option that gave it one wrote a persisted key under
    ``migrations``, and a stored "gave up on this vacuum" verdict outlives the reason
    for it: the brand it gave up on becomes supported in a later release and the repair
    never runs. Only the VOLUME changed. ``migrate_room_vocabulary``'s deferral line
    moved from WARNING to DEBUG, so an unadjudicatable target no longer shouts once per
    Home Assistant start for the life of the install.

    NOTHING ELSE MOVED, deliberately: this function still returns every unadjudicated
    target, the latch still refuses to record the migration as done while one exists,
    and stored rooms are judged exactly as before. The deferral is still retried on the
    next start — which is what makes the quieter level safe, and what a terminal
    disposition would have thrown away.

    On this house's boxes the site is currently inert: ``vacuum.robin`` (an unsupported
    Dreame) is in ``vacuums`` with a ``maps`` bucket holding zero rooms, so only the
    no-stored-rooms guard below keeps it out — one saved room away — and that box has
    already latched.

    Vacuums with no stored rooms are not targets — there is nothing to judge and nothing
    to come back for, and rooms created later are born under current rules.

    ⚠ "PRESENTED NO DECLARATION" IS NARROWER HERE THAN IN THE PLANNER — C5, STILL OPEN,
    and closing it is a CODE change (aligning the two predicates), so it is not made
    here. This function asks only "is ``room_profiles`` a NON-EMPTY DICT?"
    (``isinstance(block, dict) and block``). ``plan_room_vocabulary_migration`` applies
    that same test and then a SECOND one: ``declared_profile_fields`` over the block's
    ``builtins``/``custom_template``, with ``if not declared: continue`` — and that
    ``continue`` does not even log. So a vacuum whose adapter declares a non-empty
    ``room_profiles`` block that yields no profile FIELDS is skipped unjudged by the
    planner while this function reports it adjudicated, and the latch burns the one
    shot having judged nothing for it — the exact failure the deferred-latch design
    below was written to prevent, entering through a predicate it does not cover. It is
    the same species as the safety rule stated in the module docstring: a "cannot judge"
    result must be treated as cannot-judge by EVERY caller.
    """
    pending: list[str] = []
    for vacuum_entity_id, maps in (data.get("maps") or {}).items():
        if not isinstance(maps, dict):
            continue
        if not any(
            isinstance(bucket, dict) and (bucket.get("rooms") or {})
            for bucket in maps.values()
        ):
            continue
        block = (get_config(vacuum_entity_id) or {}).get("room_profiles")
        if not (isinstance(block, dict) and block):
            pending.append(vacuum_entity_id)
    return pending


def _apply_changes(*, data: dict[str, Any], changes: list[dict[str, Any]]) -> None:
    """Write a planned change list onto ``data``. Shared by every repair in this module.

    One applier, because the change RECORD is a replica: the planner writes it and an
    applier reads it, and a second hand-written loop would be the copy that keeps the
    old shape after the planner grows a field.
    """
    for change in changes:
        room = (
            ((data.get("maps") or {}).get(change["vacuum_entity_id"]) or {})
            .get(change["map_id"], {})
            .get("rooms", {})
            .get(change["room_id"])
        )
        if not isinstance(room, dict):
            continue
        if change["action"] == "drop":
            room.pop(change["field"], None)
        else:
            room[change["field"]] = change["new"]


def plan_room_vocabulary_migration(
    *,
    data: dict[str, Any],
    get_config,
    fields: Collection[str] | None = None,
) -> list[dict[str, Any]]:
    """Return the changes the migration WOULD make. Pure: touches nothing.

    ``get_config`` is ``adapters.registry.get_adapter_config``, injected so this stays
    importable without the registry and testable without registering an adapter.

    ``fields`` narrows the judgement to a subset of the vocabulary axes, for a repair
    scoped to ONE axis whose option list changed after the broad repair's latch was
    spent (``migrate_path_type_residue`` below). It is an INTERSECTION with
    ``_VOCABULARY_FIELDS``, never a replacement for it: a caller cannot name a field
    that is not a vocabulary axis and have it judged, because ``name`` and ``room_id``
    sit in the same dict and judging them would strip a room's identity.
    """
    planned: list[dict[str, Any]] = []
    judged_fields = tuple(
        f for f in _VOCABULARY_FIELDS if fields is None or f in fields
    )

    for vacuum_entity_id, maps in (data.get("maps") or {}).items():
        if not isinstance(maps, dict):
            continue
        config = get_config(vacuum_entity_id) or {}
        block = config.get("room_profiles")
        if not isinstance(block, dict) or not block:
            # No declaration to judge against. Skipping is the only safe act — an
            # unregistered or undeclared adapter must never license edits to stored
            # rooms.
            _LOGGER.debug(
                "vocabulary_migration: %s declares no room_profiles; skipped",
                vacuum_entity_id,
            )
            continue

        vocabulary = config.get("vocabulary") or {}
        declared = declared_profile_fields(
            {"builtins": block.get("builtins") or {}, "custom_template": block.get("custom_template")}
        )
        if not declared:
            continue
        default_profile = (block.get("builtins") or {}).get(block.get("default_profile")) or {}

        for map_id, bucket in maps.items():
            if not isinstance(bucket, dict):
                continue
            for room_id, room in (bucket.get("rooms") or {}).items():
                if not isinstance(room, dict):
                    continue
                for field in judged_fields:
                    if field not in room:
                        continue
                    if field not in declared:
                        planned.append({
                            "vacuum_entity_id": vacuum_entity_id,
                            "map_id": str(map_id),
                            "room_id": str(room_id),
                            "field": field,
                            "action": "drop",
                            "old": room[field],
                            "new": None,
                        })
                        continue
                    allowed = _option_values(vocabulary, field)
                    if allowed is None or str(room[field]) in allowed:
                        continue

                    # A RETIRED value the brand still declares an alias for keeps its
                    # MEANING — resolve it before considering the default. Without
                    # this, Eufy's "Standard" (the original middle pass density, and
                    # the initial value of the very first setup) fell through to the
                    # default profile's "Quick", moving every affected room from the
                    # middle density to the fastest. A reduction in cleaning nobody
                    # chose, and invisible because the result was a perfectly valid
                    # value.
                    replacement = _alias_target(vocabulary, field, room[field], allowed)
                    if replacement is None:
                        replacement = default_profile.get(field)
                    if replacement is None or str(replacement) not in allowed:
                        # The brand's own default is not in its own option list. That
                        # is an adapter defect, and guessing past it would hide it.
                        _LOGGER.warning(
                            "vocabulary_migration: %s room %s has out-of-vocabulary %s=%r "
                            "but the default profile offers no valid replacement (%r); left alone",
                            vacuum_entity_id, room_id, field, room[field], replacement,
                        )
                        continue
                    planned.append({
                        "vacuum_entity_id": vacuum_entity_id,
                        "map_id": str(map_id),
                        "room_id": str(room_id),
                        "field": field,
                        "action": "reset",
                        "old": room[field],
                        "new": replacement,
                    })

    return planned


def migrate_room_vocabulary(
    *,
    data: dict[str, Any],
    get_config,
    force: bool = False,
) -> dict[str, Any]:
    """Apply the migration once, recording that it ran ONLY IF IT COULD JUDGE
    EVERY TARGET. Idempotent.

    Recording is conditional, not automatic: the deferred-latch block below sets
    ``migrations[MIGRATION_KEY]`` only when ``_unadjudicated_targets`` comes back
    empty. Otherwise it deliberately DECLINES to record, logs at DEBUG, and leaves
    the run to be retried on the next start — "missing runtime information is
    DEFERRED, never SUCCESS", the file's most carefully argued behaviour.
    ⚠ was: "Apply the migration once, recording that it ran" — the opposite of that
    rule, and it is the line a caller reads.

    RETURN SHAPE, and it is NOT uniform across the two exits:

      * the run path returns FOUR keys —
        ``{"ran": True, "changes": [...], "rooms_touched": int, "latched": bool}``;
      * the already-migrated early return (``migrations[MIGRATION_KEY]`` set and
        ``force`` false) returns ``{"ran": False, "changes": [], "rooms_touched": 0}``
        with NO ``latched`` key, so ``result["latched"]`` raises KeyError there.
        Read it with ``.get("latched")``.

    ⚠ was: a three-key enumeration that omitted ``latched`` entirely. That
    enumeration is the contract a caller codes against, and ``latched`` is the ONLY
    signal that a run deferred.

    The caller is responsible for persisting ``data``; nothing here writes to disk.
    """
    migrations = data.setdefault("migrations", {})
    if migrations.get(MIGRATION_KEY) and not force:
        return {"ran": False, "changes": [], "rooms_touched": 0}

    changes = plan_room_vocabulary_migration(data=data, get_config=get_config)
    _apply_changes(data=data, changes=changes)

    # LATCH ONLY IF THIS RUN COULD ACTUALLY SEE SOMETHING.
    #
    # This used to be unconditional, and a run that repaired nothing still burned the
    # one shot. That is reachable on a normal cold boot: the adapters are registered
    # from the vacuum entities of OTHER integrations, and if those have not finished
    # setting up, every vacuum here is skipped for want of a declaration. The repair
    # then marked itself done having judged nothing, and the rooms it was written to
    # heal kept their bad values permanently — silently, because the skip logs at DEBUG.
    # Observed on hardware: two full restarts changed nothing, and a config-entry
    # RELOAD (by which point the vacuums existed) repaired all twenty rooms.
    #
    # The rule is EVERY target, not "any adapter answered". With two vacuums, one
    # provider being ready must not burn the opportunity for a provider that starts
    # later: a first draft latched as soon as a single declaration was found, which on
    # this very install would have repaired the Eufy and abandoned the Roborock. The
    # invariant is that a migration is complete only when every target it is responsible
    # for has reached a terminal disposition; missing runtime information is DEFERRED,
    # never SUCCESS.
    #
    # A vacuum with no stored rooms is not a target, so an install with none latches
    # vacuously rather than rescanning forever.
    _pending = _unadjudicated_targets(data=data, get_config=get_config)
    _latched = not _pending
    if _latched:
        migrations[MIGRATION_KEY] = True
    else:
        # DEBUG, NOT WARNING — downgraded 2026-08-24 by the C61 ruling.
        #
        # The failure mode this line had: a vacuum on an UNSUPPORTED brand can never be
        # adjudicated. ``brands.resolve_brand`` registers no adapter for it while the
        # vacuum stays managed, so ``get_config`` returns None forever, ``_pending``
        # never empties, and this message was re-emitted at WARNING on EVERY Home
        # Assistant start, permanently, with nothing the user could do about it.
        # (``vacuum.robin``, the unsupported Dreame on this house's boxes, is one saved
        # room away from being exactly that.) A warning that can never be acted on and
        # never stops trains people to mute the integration's log, which costs them the
        # warnings that DO mean something.
        #
        # The information is not gone, it is just not shouted: the full count and the
        # entity ids stay here for anyone debugging a repair that has not happened, and
        # every caller still gets ``latched: False`` in the return value. The latch
        # condition itself is untouched — this run still did not record itself as done
        # and still retries on the next start.
        _LOGGER.debug(
            "vocabulary_migration: %d vacuum(s) with stored rooms had no adapter "
            "declaration to judge against (%s), so their rooms could not be evaluated; "
            "NOT recording the migration as done — it will retry on the next start",
            len(_pending), ", ".join(_pending),
        )

    touched = len({(c["vacuum_entity_id"], c["map_id"], c["room_id"]) for c in changes})
    if changes:
        _LOGGER.info(
            "vocabulary_migration: repaired %d setting(s) across %d room(s) written under "
            "the framework's former Eufy default", len(changes), touched,
        )
        for c in changes:
            _LOGGER.info(
                "vocabulary_migration:   %s room %s: %s %s=%r%s",
                c["vacuum_entity_id"], c["room_id"], c["action"], c["field"], c["old"],
                f" -> {c['new']!r}" if c["action"] == "reset" else "",
            )

    return {
        "ran": True,
        "changes": changes,
        "rooms_touched": touched,
        # False means this run declined to record itself as done and will retry.
        "latched": _latched,
    }


# ---------------------------------------------------------------------------
# The path_type residue — a SECOND, narrower repair with its own key
# ---------------------------------------------------------------------------
#
# v2.2.4 (`8b44bc24`) replaced Roborock's `path_type` option list `wide`/`narrow` with
# `standard`/`deep`/`deep_plus`, and its own comment asserts that the repair above
# "RESETS it on the next pass". It does not, and could not: `room_vocabulary_v1` ships
# since v2.0.0 and LATCHES on first boot, so on every install that existed before the
# list changed the one shot was already spent. Measured on this house's box: all twelve
# of `vacuum.ivy`'s rooms still carry `path_type: "wide"` with
# `migrations.room_vocabulary_v1: True` beside them. A value no option matches, no
# picker can change, and the dispatch filter silently drops.
#
# The in-tree precedent for the right move is `maintenance_component_renames_v3`, whose
# key carries "BUMP THIS WHENEVER YOU ADD A ROW" — the opposite of `MIGRATION_KEY`'s
# "only bump if the RULES change".
#
# WHY A NEW KEY AND NOT A BUMP OF `room_vocabulary_v1`, which was the obvious move and
# is the dangerous one. Bumping re-opens EVERY axis on EVERY brand against TODAY's
# option lists. Dry-run against this house's real storage, both planners over the same
# data: this repair plans 12 changes, all of them the intended path_type resets. The
# broad one plans 13 — the same 12 plus `fan_speed: "Max"` -> `"balanced"` on one of
# ivy's rooms. Not "max": there is no alias, so the default profile supplies the answer
# and a room somebody set to the FASTEST suction silently drops to the middle one. A
# cleaning regression, invisible, in a migration that was asked to fix a route value.
#
# ⚠ 13 IS A FLOOR, NOT A TOTAL. The probe judged only the brand whose option lists are
# module constants; Eufy assembles its lists inside `adapter.py` and no Dreame config
# was supplied, so `vacuum.alfred` and `vacuum.robin` were unjudgeable in it and
# contributed nothing. Both carry display-cased values on disk (`clean_mode: "Vacuum
# and mop"`, `water_level: "32"`) that a live broad run would judge. The bound argues
# the same way whichever side it moves: one list changed, so one field is repaired.
#
# This repair therefore does RESETS ONLY. A DROP means "the brand has no such axis",
# which is the broad repair's question, judged under the broad repair's latch; a
# narrow repair that also dropped would be re-adjudicating the very thing it exists to
# avoid, through a smaller door.

#: Bump to re-run. Unlike ``MIGRATION_KEY``, the rule for THIS one is the rule
#: ``maintenance_component_renames_v3`` states: a new key per residue, because the
#: trigger is an option LIST that changed under stored data, not a change of rules.
RESIDUE_MIGRATION_KEY = "room_path_type_residue_v1"

#: The one axis v2.2.4 re-spelled. Adding a field here does NOT repair it — the latched
#: key above would skip the run entirely on every install that has already seen it. A
#: new residue needs a new key.
RESIDUE_FIELDS: tuple[str, ...] = ("path_type",)


#: The water ladder is now READ off `select.<obj>_mop_intensity` rather than declared
#: (issue #71), so a machine whose rungs are off/mild/standard/intense retires our
#: transcribed low/medium/high. Its own key, because `room_path_type_residue_v1` has
#: already latched on every install that has seen it — adding a field to that tuple
#: would repair nothing.
WATER_RESIDUE_MIGRATION_KEY = "room_water_level_residue_v1"
WATER_RESIDUE_FIELDS: tuple[str, ...] = ("water_level",)


def plan_residue_repair(
    *, data: dict[str, Any], get_config, fields: Collection[str]
) -> list[dict[str, Any]]:
    """Return the RESETS a narrow repair would make for ``fields``. Pure.

    Every safety rule of the broad repair still applies, because this is the same
    planner: no declaration means skip, no option list means "cannot judge", a declared
    alias carries a retired value's meaning, and a default that is not in the brand's
    own options is reported rather than written.

    RESETS ONLY. A DROP answers "does this brand have the axis at all?", which is the
    broad repair's question under the broad repair's latch; a narrow repair that also
    dropped would re-adjudicate the very thing it exists to avoid, through a smaller
    door.
    """
    return [
        change
        for change in plan_room_vocabulary_migration(
            data=data, get_config=get_config, fields=fields
        )
        if change["action"] == "reset"
    ]


def plan_path_type_residue_repair(
    *, data: dict[str, Any], get_config
) -> list[dict[str, Any]]:
    """The ``path_type`` instance of :func:`plan_residue_repair`."""
    return plan_residue_repair(data=data, get_config=get_config, fields=RESIDUE_FIELDS)


def plan_water_level_residue_repair(
    *, data: dict[str, Any], get_config
) -> list[dict[str, Any]]:
    """The ``water_level`` instance of :func:`plan_residue_repair`."""
    return plan_residue_repair(
        data=data, get_config=get_config, fields=WATER_RESIDUE_FIELDS
    )


def _migrate_residue(
    *, data: dict[str, Any], get_config, key: str, fields: Collection[str],
    label: str, force: bool = False,
) -> dict[str, Any]:
    """Run one narrow repair. Shared so two axes cannot drift apart.

    Independent of ``migrate_room_vocabulary`` in every direction: its own key, so a
    spent ``room_vocabulary_v1`` does not skip this, and a spent key here does not skip
    that. Returns the same shape as ``migrate_room_vocabulary``, including the
    ``latched`` key being ABSENT on the already-migrated early return.

    The caller persists ``data``; nothing here writes to disk.
    """
    migrations = data.setdefault("migrations", {})
    if migrations.get(key) and not force:
        return {"ran": False, "changes": [], "rooms_touched": 0}

    changes = plan_residue_repair(data=data, get_config=get_config, fields=fields)
    _apply_changes(data=data, changes=changes)

    # Same deferred-latch rule as ``migrate_room_vocabulary`` — see the long note there
    # for why recording is conditional. It applies unchanged: this repair is judged
    # against a DECLARATION too, so a cold boot whose vacuum providers have not set up
    # yet must not burn this key either.
    _pending = _unadjudicated_targets(data=data, get_config=get_config)
    _latched = not _pending
    if _latched:
        migrations[key] = True
    else:
        _LOGGER.debug(
            "%s: %d vacuum(s) with stored rooms had no adapter declaration to judge "
            "against (%s); NOT recording the repair as done — it will retry on the "
            "next start",
            label, len(_pending), ", ".join(_pending),
        )

    touched = len({(c["vacuum_entity_id"], c["map_id"], c["room_id"]) for c in changes})
    if changes:
        _LOGGER.info(
            "%s: reset %d stored value(s) across %d room(s) that the brand's current "
            "option list no longer declares", label, len(changes), touched,
        )
        for c in changes:
            _LOGGER.info(
                "%s:   %s room %s: %s=%r -> %r",
                label, c["vacuum_entity_id"], c["room_id"], c["field"], c["old"], c["new"],
            )

    return {
        "ran": True,
        "changes": changes,
        "rooms_touched": touched,
        "latched": _latched,
    }


def migrate_path_type_residue(
    *, data: dict[str, Any], get_config, force: bool = False
) -> dict[str, Any]:
    """Reset a stored ``path_type`` the brand no longer declares. Idempotent.

    v2.2.4 replaced Roborock's list ``wide``/``narrow`` with
    ``standard``/``deep``/``deep_plus`` and bumped no key, so the broad repair's one
    shot was already spent on every install that predated it.
    """
    return _migrate_residue(
        data=data, get_config=get_config, key=RESIDUE_MIGRATION_KEY,
        fields=RESIDUE_FIELDS, label="path_type_residue", force=force,
    )


def migrate_water_level_residue(
    *, data: dict[str, Any], get_config, force: bool = False
) -> dict[str, Any]:
    """Carry a stored ``water_level`` onto the device's own ladder. Idempotent.

    Issue #71: the Roborock water vocabulary is now READ off
    ``select.<obj>_mop_intensity`` rather than transcribed from one S6. On a machine
    whose rungs are off/mild/standard/intense, a room stored ``medium`` is suddenly out
    of vocabulary.

    ⚠ THIS REPAIR IS ONLY SAFE BECAUSE THE BRAND DECLARES POSITIONAL ALIASES. Without
    them the planner falls back to the brand's ``default_profile``, which for Roborock
    is ``vacuum_quick`` — ``water_level: "off"``. The "repair" would then silently stop
    the mop in every room somebody had set to medium or high: a valid stored value, a
    clean migration log, and a floor that never gets washed again. ``_alias_target`` is
    consulted BEFORE the default for exactly this case, and
    ``roborock/vocabulary.py::build_positional_aliases`` supplies the map.
    """
    return _migrate_residue(
        data=data, get_config=get_config, key=WATER_RESIDUE_MIGRATION_KEY,
        fields=WATER_RESIDUE_FIELDS, label="water_level_residue", force=force,
    )
