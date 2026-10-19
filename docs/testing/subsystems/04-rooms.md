# 04 — Rooms — Subsystem Test Map

The rooms subsystem owns room discovery, the managed-room CRUD lifecycle, and the
**access graph** (which rooms grant cleaning access to which, plus the rule
engine that gates/modifies rooms at start). Covered by **399 tests across 12 files**.

Source: `custom_components/eufy_vacuum/rooms/`
Architecture reference: [17 — A Room's Identity](../../dev/17-room-identity.md), [18 — The Access Graph](../../dev/18-access-graph.md)


### `vocabulary_migration.py` — the one-shot repair (added 2026-08-07)

Removing the framework's Eufy-shaped profile default is prophylactic: a stored
per-room field outranks the profile, so rooms already on disk keep the bad value
indefinitely. This module is the curative half, run once after adapter
registration (it needs each brand's DECLARATION, which does not exist until
then, so it cannot be a versioned store migration).

Two rules, both declaration-driven: **DROP** a field no declared profile carries,
**RESET** a value absent from the brand's declared options to that brand's
`default_profile` value. No nearest-match — the option lists are declared sets
with no ordering to be nearest in.

`test_vocabulary_migration.py` (19 tests) weights the refusals as heavily as the
repairs, because this rewrites real user rooms and an over-reach is silent:

| id | what it holds |
|---|---|
| `MIG-1` / `MIG-2` | DROP an undeclared axis; RESET an out-of-vocabulary value |
| `MIG-2b` | RESET takes the DECLARED default, never the lexically nearest option |
| `MIG-3` | a correct room comes through byte-identical |
| `MIG-4` | a vacuum whose adapter declares nothing is skipped, never guessed at |
| `MIG-5` | **the check that averted a destructive migration** — see below |
| `MIG-6` | a brand whose own default is invalid is reported, not worked around |
| `MIG-7` | idempotent; a user's deliberate re-edit is not "repaired" on next boot |
| `MIG-8` | planning is pure, so the change can be reviewed before it runs |
| `MIG-9` | the retired-value fold is subsumed with NO retired-value map |
| `MIG-10a` | a retired value the brand still ALIASES keeps its meaning, not the default |
| `MIG-10b` | with no alias it still falls back to the brand's default |
| `MIG-10c` | an alias pointing at an undeclared option is ignored, never written |
| `MIG-11` | **a run that could not evaluate every target does not latch** — see below |
| `MIG-12` | an UNADJUDICATABLE target defers at DEBUG, not WARNING — see below |

**MIG-5 is the one to read.** An early draft keyed DROP on "the brand declares no
options for this field". That reads correct and would have stripped `clean_mode`
and `water_level` from every room on a Roborock S6 — which declares no options for
them because its mop is not settable, not because the axis does not exist. Absence
of an OPTION LIST means "cannot judge"; only absence from the brand's own PROFILES
means "no such axis". Caught by enumerating the live store before the rule was
written: a guard that newly activates over existing data must be measured against that
data first, because passing your own tests says nothing about what is already on disk.

**The DROP must also be durable, and originally was not.** Found on hardware
2026-08-08: the migration correctly dropped `clean_intensity` from all ten Roborock
rooms, and then a plain save of every room put it straight back as `""`.
`normalize_room_profile` always emits all nine `ProfileRecord` keys and
`_finalize_room_update` writes that result to the room, so the repair was being undone
one room at a time — inert (empty, never dispatched, no control rendered), which is
precisely why it would have gone unnoticed until the axis quietly existed everywhere
again. `_finalize_room_update` now strips undeclared axes on save using the SAME
discriminator (`room_profiles.declared_profile_fields`), so the two paths cannot
diverge again. Pinned by `PM-30` / `PM-30b` in `test_profiles_manager.py`, both
mutation-verified.

**MIG-11 separates "could not evaluate yet" from "completed", which the one-shot
originally conflated.** The flag was set unconditionally, so a run that repaired
nothing still burned the single opportunity. That is reachable on an ordinary cold
boot: adapters are registered from vacuum entities owned by OTHER integrations, and if
those have not finished setting up, every vacuum is skipped for want of a declaration —
the same branch MIG-4 exercises, which pinned the skip but never what the skip did to
the flag. Found on hardware 2026-08-08: two full restarts repaired nothing, and a
config-entry reload — by which point the vacuums existed — repaired all twenty rooms.

The invariant is that a migration is complete only when **every** target it is
responsible for has reached a terminal disposition; missing runtime information is
DEFERRED, never SUCCESS. `MIG-11` pins all three states, and the middle one is the
subtle one: with two vacuums on two providers, latching as soon as *any* declaration
appears repairs the ready brand and abandons the slower one permanently. A vacuum with
no stored rooms is not a target, so an empty install latches vacuously instead of
rescanning forever. Both wrong answers are mutation-verified — restoring the
unconditional latch reddens two of the three, and restoring "latch if any adapter
answered" reddens the partial-readiness case alone.

Deferral only helps if the work later happens, and HA offers no "after that
integration" hook to wait on. The call site therefore runs the repair from
`async_at_started` rather than inline in `async_setup_entry` — it fires once everything
has set up, and fires immediately when HA is already running, so a live reload still
repairs promptly. `listeners/discovery.py` already used that primitive for the same
reason (`get_maps` is not registered at setup time); this call site was its forgotten
sibling.

**MIG-12 pins the VOLUME of that deferral, which MIG-11 does not.** The latch was
designed against a cold-boot RACE, where waiting works. It was never reconciled with
the unsupported-brand arm that shipped later: `brands.resolve_brand` registers no
adapter for an unsupported vacuum while the vacuum stays managed, so `get_config`
returns `None` forever, the target is pending on every run, and the deferral message
was re-emitted at WARNING on every Home Assistant start for the life of the install.
Ruled 2026-08-24 (C61): downgrade the line to DEBUG and give the target no terminal
disposition — a persisted "gave up" verdict outlives its reason once the brand becomes
supported. MIG-12 asserts both directions, because a downgrade that dropped the
message would pass a bare "no warning" check while destroying the only record a
diagnoser has, and it re-asserts the latch so a quieter line that also stopped
retrying cannot pass as this fix. Ablated: restoring `_LOGGER.warning` reddens it.

**MIG-9 is why `normalize_clean_intensity` could be deleted rather than moved.**
It folded the retired Eufy values `standard`/`normal` to `"Quick"` on every read,
from nine call sites, to repair data written before 2026-07-26 — and that data was
still on disk twelve days later, because rooms are only rewritten when edited. The
migration needs no retired-value map to subsume it: `Standard` is simply absent
from Eufy's declared `clean_intensity_options`, so the generic RESET catches it and
Eufy's own `default_profile` supplies `Quick`. Same answer, from a declaration.

### The `path_type` residue — a second, narrower repair (added 2026-10-18)

The one-shot above has a blind spot its own comment denied. v2.2.4 (`8b44bc24`)
replaced Roborock's `path_type` option list `wide`/`narrow` with
`standard`/`deep`/`deep_plus` and asserted the migration "RESETS it on the next pass".
It did not and could not: `room_vocabulary_v1` ships since v2.0.0 and latches on first
boot, so on every install that predates the list change the one shot was already spent.
Measured on the maintainer's box: all twelve of `vacuum.ivy`'s rooms still carried
`path_type: "wide"` with `room_vocabulary_v1: True` beside them — a value no option
matches, no picker can change, and the dispatch filter silently drops.

`MIGRATION_KEY`'s comment says "only bump if the RULES change", which is why nobody
bumped it. The in-tree precedent that fits is `maintenance_component_renames_v3`:
**"BUMP THIS WHENEVER YOU ADD A ROW"** — a new key per residue, because the trigger is
an option LIST changing under stored data, not a change of rules.

**Why a second key rather than a bump, and this is the whole design.** Bumping
re-opens every axis on every brand against today's lists. Both planners were dry-run
over the same real storage: the narrow repair plans **12** changes, all of them the
intended resets; the broad one plans **13** — the extra being `fan_speed: "Max"`
falling to the default profile's `balanced` on one room. There is no alias for `Max`,
so the default supplies the answer and a room somebody set to the fastest suction
silently drops to the middle. A cleaning regression, with no error, inside a migration
asked to fix a route value. (13 is a floor: the probe could only judge the brand whose
option lists are module constants, so Eufy and Dreame contributed nothing to it.)

`test_path_type_residue_migration.py` (11 tests) therefore spends most of its assertions on what
the repair declines to do. Nine of the eleven are ablation-verified; PTR-11 is a set
containment and PTR-2 rides PTR-1's parametrize:

| id | what it holds |
|---|---|
| `PTR-1` / `PTR-2` | both values v2.2.4 retired are repaired — by the DECLARATION, not by knowing the string `wide` |
| `PTR-3` | **the narrowing** — out-of-vocabulary `clean_mode` and `fan_speed` in the same room are left alone, and the broad planner is run over that same room to prove the collateral is real |
| `PTR-4` | an in-vocabulary `path_type` is not re-adjudicated |
| `PTR-5` | **resets only, never drops** — an Eufy room's `path_type` is a DROP (Eufy declares the axis in no profile) and this repair must not answer that question |
| `PTR-6` | a spent `room_vocabulary_v1` does not skip it — the upgrader's real state, and the reason for a second key |
| `PTR-7` | idempotent; the second run reports `ran: False` |
| `PTR-8` | an unjudgeable target DEFERS without burning the key (the MIG-11 rule, inherited) |
| `PTR-9` | `fields` INTERSECTS the vocabulary axes rather than replacing them |
| `PTR-10` | no declared option list still means "cannot judge" (the MIG-5 rule, inherited) |
| `PTR-11` | every axis named in `RESIDUE_FIELDS` is a real vocabulary axis — a rename would narrow the repair to nothing, silently |

**PTR-9 is the one that is easy to skip.** The narrowing is implemented as a `fields`
filter on the shared planner, and the obvious spelling — `for field in (fields or
_VOCABULARY_FIELDS)` — lets a caller name `name` or `room_id`, which sit in the same
dict as the settings and appear in no option list. Every room would be stripped of its
name. The filter is an intersection with `_VOCABULARY_FIELDS` for that reason.

### The `water_level` residue — the same shape, with a sharper edge (added 2026-10-19)

`adapters/roborock` now READS its water ladder off `select.<obj>_mop_intensity` instead
of declaring a transcript of one S6 (issue #71 — see
[15 — adapters](15-adapters.md)). On a Saros 10 the rungs are
`off/mild/standard/intense/extreme`, so a room stored `water_level: "medium"` is
suddenly out of vocabulary. Same residue shape as `path_type`, so
`test_water_level_residue_migration.py` reuses the same generalised machinery under its
own key, `room_water_level_residue_v1`.

**What makes this one sharper is where the fallback leads.** The broad repair resets an
out-of-vocabulary value to the brand's `default_profile`, and Roborock's default profile
is `vacuum_quick`, whose `water_level` is **`off`**. So the obvious repair turns every
room somebody set to medium or high into a room that does not mop — a valid stored
value, a clean migration log, no error anywhere, and a floor that never gets washed
again. The `path_type` repair's collateral was a room cleaning *less*; this one stops
cleaning.

The brand therefore declares **positional aliases**, which `_alias_target` consults
*before* the default: index 2 of the retired ladder becomes index 2 of the live one,
because on an ascending ladder position IS the meaning. Roborock declines an alias for
`path_type: "wide"` for the opposite reason — nobody picked `wide`, so there is no
intent to carry forward. Somebody did pick `medium`.

| id | what it holds |
|---|---|
| `WLR-1` | a retired rung keeps its position — `low→mild`, `medium→standard`, `high→intense`, parameterized so a mapping right in the middle and wrong at the ends cannot pass |
| `WLR-2` | **the alias is load-bearing** — same room, same repair, alias declaration removed, and the value becomes `off`. An assertion about the BAD outcome, so dropping the alias is loud instead of quiet |
| `WLR-3` | a rung the device still has is left alone |
| `WLR-4`/`WLR-5` | its own key — neither a spent `room_vocabulary_v1` nor a spent `room_path_type_residue_v1` skips it |
| `WLR-6` | idempotent |
| `WLR-7` | NARROWING: `path_type` and `fan_speed` on the same room are untouched |
| `WLR-8` | an unjudgeable target defers without burning the key (the MIG-11 rule, inherited) |
| `WLR-9` | the mapping is asserted against the INDEX, not a transcript, so it cannot agree with a hand-written table that drifted |
| `WLR-10` | a SHORTER device ladder clamps down, never up — under-mop over wet-mop, the asymmetry `mixed_mode_water_policy: "safest"` already rests on |
| `WLR-11` | identical ladders declare no aliases, so the S6 is inert |

All eleven are ablation-verified. `WLR-2` needed a red input of its own, and finding it
is the useful part: because it asserts the *unwanted* outcome, no alias ablation can
redden it — mapping every rung to the top, to the bottom, or leaving short-ladder rungs
unmapped all leave WLR-2 green. Removing the default-profile fallback is what reddens
it, which is the honest statement of what it pins: not "aliases work" but "this is where
the value goes when they do not".

**The two repairs share one implementation.** `plan_residue_repair` and
`_migrate_residue` are parameterized by (key, fields); `path_type` and `water_level` are
instances. A second hand-written copy is how the two would drift on the change-record
shape, and the ablation harness runs both suites together for that reason — restoring
the unconditional latch reddens `PTR-8` and `WLR-8` together.

**PTR-5 needed a second attempt to bite.** Written first against a Roborock room
carrying `clean_intensity`, it passed with the reset-only filter deliberately removed —
because the `fields` filter already stopped `clean_intensity` from being iterated at
all, so no DROP was ever planned and the assertion tested nothing. The live shape for
a DROP under a `path_type`-only filter is an **Eufy** room: Eufy declares the axis in
no profile (a deliberate subtraction — it is the second name for `clean_intensity`).
Rewritten against that, the ablation reddens.

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer | Mocking |
|---------------|------:|----:|------------|-------|-------|
| `access_graph.py` | 462 | 94% | `test_access_graph.py`, `test_manager_rooms.py` | integration | clean |
| `room_crud.py` | 159 | 93% | `test_room_crud.py`, `test_manager_rooms.py` | integration | **bare x1** |
| `room_discovery.py` | 167 | 93% | `test_room_discovery.py` | integration | clean |
| `reconciliation.py` | 154 | 80% | `test_rooms_reconciliation.py` (unit), `test_rooms_reconcile.py` | integration | **bare x1** |
| `source_refresh.py` | 161 | 88% | `test_rooms_source_refresh.py` (unit) | unit | clean |
| `room_manager.py` | 82 | 96% | `test_room_manager.py` (unit) | unit | clean |
| `room_defaults.py` | 21 | 100% | `test_room_manager.py` (unit) + `test_adapter_contract.py` | unit | clean |
| `utils.py` | 3 | 100% | `test_rooms_utils.py` (unit) | unit | clean |
| `vocabulary_migration.py` | 96 | 91% | `test_vocabulary_migration.py`, `test_path_type_residue_migration.py` (unit) | unit | clean |

(Room-facing services live in [17 — services](17-services.md):
`test_services_rooms.py`, `test_services_access_graph.py`.)

---

## What's tested

- **Access graph** (`AG`) — grants normalization (dedup, self-exclude, invalid),
  rule normalization, full validation across every structural issue type
  (cycle / duplicate / missing / self-reference / multiple-inbound), graph-state
  classification, the room-rule match operators (exists / on-off / in / numeric),
  health report, and the **editable-target selectability** builder
  (`get_room_access_editor`): a target whose edge would close a loop is
  not-selectable with a reason; an illegal-but-unnamed-here candidate falls back
  to the generic legality reason.
- **CRUD** (`RC`) — `discover_rooms` (runs discovery, caches payload, points the
  runtime at the active map), `save_managed_rooms`, `get_managed_rooms`,
  `rebuild_map`, and `remove_map` including the cleanup tail (history / rule-status
  / active-job slots cleared, remaining maps' grant lists walked).
- **Discovery** (`RD`) — adapter-config-driven room extraction: active-map id
  resolution, normalize + dedup + skip-bad-row, payload wrapping.
- **Reconciliation** (`RR`) — `compute_reconciliation` slug-vs-id identity-shift
  detection (`id_changed` when a known slug carries a new segment id;
  `renamed` when a known id carries a new name/slug), int-coercion and
  slug-derivation guards, and `plan_migration` producing the data move a
  confirmed review applies (the manager owns the dict mutation; this module is
  pure). New/removed rooms are deliberately out of scope (owned by
  `setup/drift.py`).
- **New-room defaults** (`room_defaults.py`, via `test_room_manager.py` +
  the adapter contract suite) — `resolve_new_room_defaults` is THE single
  answer for what a freshly-created room starts with (it replaced four
  independently hand-maintained copies of the Eufy literals), resolved through
  the adapter so a Roborock room is not created with Eufy display vocabulary;
  `build_managed_rooms` takes the result as a **required** `new_room_defaults`
  argument (a permissive default there would re-open the hole).
- **Source refresh** (`SR`) — the `service_response` discovery source (Roborock
  `get_maps`): `flatten_maps_response` normalizes `{segment_id: name}` into the
  same list-of-dicts shape the attribute source carries (keyed by map name),
  `async_refresh_room_source` calls the service at the async boundaries and
  caches it, and `get_cached_room_source` is what the sync discovery path reads
  instead of an entity attribute.

---

## How it's tested

`AccessGraphManager(data, hass)` over a hand-built `data["maps"]` tree with
`_room(...)` / `_rooms(...)` helpers; `RoomMapManager` against a MagicMock
manager for pure CRUD and the real `manager` fixture where discovery needs live
`hass` states.

---

## Known gaps

`reconciliation.py` (78%) is currently the thin spot in this subsystem — well
below the others. Its uncovered branches (missing lines 44-45, 93, 118, 123,
175-177, 190-192, 226, 258, 262, 295-305, 317, plus the paired branch misses at
those same sites) are concentrated in three real behavior arms, not defensive
plumbing:
- the `renamed_and_renumbered` single-unmatched-pair review (the
  `len(unmatched_existing) == 1 and len(unmatched_discovered) == 1` branch
  around line 175),
- the matching single-pair settings **carry-forward** in `plan_migration`
  (the `leftover_existing_slugs`/`unmatched_discovered` single-match branch
  around line 295 — the old id's durable settings moving onto the new id),
- and the dismissed-plan-token short-circuit (`dismissed_at is not None and
  reviews and dismissed_plan_token is not None`, line 190).
These are the natural next tests for this subsystem — run
`--cov-report=term-missing` on `rooms/reconciliation.py` for the current line
list before adding them, since the exact numbers will keep moving as the file
changes.

`access_graph.py` (94%) and `room_discovery.py` (93%) leave mostly
type-coercion fallbacks and duplicated skip-bad-row branches — the `(TypeError,
ValueError)` `except` blocks themselves are covered; what is not is the
*fallback* arms that replace a non-list / non-dict input with `[]` / `{}` and
the `continue` skip-bad-row guards repeated across the graph walkers
(`access_graph.py` missing lines 154, 160, 211, 246, 287, 290, 500, 503, 521,
849, 852, 858, 864, 1100, 1112; `room_discovery.py` missing lines 147, 235,
240, 248, 252, 264, 280, 286). These are normalization plumbing, not behavior.

One genuine but minor behavior branch remains untested:
`access_graph.py` around lines 685-698 — the per-issue-type editable-target
reason strings (duplicate / missing / self-reference / multiple-inbound) in
`get_room_access_editor`. The editor is tested for the loop reason and the
generic legality fallback (see "What's tested"); the four named per-type reason
strings are deliberately left unexercised — they are unreachable elif-arms
already covered by the generic-fallback test. Also uncovered: one
effectively-unreachable cycle-DFS artifact (`access_graph.py` ~964, the
`cycle_chain = [room_id]` else branch) and the `_single_cached_map_id`
non-list-of-dicts-segments guard (`return None`) in `room_discovery.py`
(147) — part of the issue-#46 single-map anchor fallback, not
pragma-excluded.

(Exact line numbers above are from a fresh coverage run against this
worktree's revision and will drift as the modules change — treat the
*shape* of each gap, not the line number, as the durable fact.)
