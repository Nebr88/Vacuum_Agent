<!-- GENERATED FILE — DO NOT EDIT BY HAND. Regenerate: python scripts/gen_bn_catalog.py -->

# BN catalog — every break-notation anchor, by file

A `BN` anchors a **place**, not a claim — a region of a file that prose can address without the file being split. This is the card catalog of them: where each one is, the name on the line beneath it, and which documents cite it. The rule for when a divider earns one is in [design/shipped/notation-anchors.md](../design/shipped/notation-anchors.md) § `BN`.

**177 anchors in 38 files · 5 cited by at least one document · 0 with no name line.**

The tokens below are *data* — this file is excluded from the citation scan so listing an anchor here does not count as citing it. Cite from prose as `path#TOKEN` in backticks; the catalog deliberately never uses that form.

## `custom_components/eufy_vacuum/__init__.py` · 2

| line | token | section | cited by |
|---:|---|---|---|
| 145 | BNACE45Q | Domain setup | — |
| 291 | BNMENBE8 | Config entry lifecycle | — |

## `custom_components/eufy_vacuum/adapters/eufy/constants.py` · 6

| line | token | section | cited by |
|---:|---|---|---|
| 35 | BNRD9B1V | Mop wash debounce | — |
| 63 | BNWC83XR | Post-job water amendment timeout | — |
| 78 | BNM86HVH | Battery | — |
| 90 | BNGEQ16P | Water flow rates | — |
| 106 | BNKGEF7P | Physical tank measurements | — |
| 128 | BNZEYNKY | Wash frequency interval bounds | — |

## `custom_components/eufy_vacuum/adapters/eufy/vocabulary.py` · 1

| line | token | section | cited by |
|---:|---|---|---|
| 263 | BNZZZXW7 | Fault policy (RF-DOCK) -- SOURCE, and whether the fault invalidates cleaning evidence | — |

## `custom_components/eufy_vacuum/battery/job_metrics.py` · 1

| line | token | section | cited by |
|---:|---|---|---|
| 148 | BNWM5EZD | Helpers | — |

## `custom_components/eufy_vacuum/const.py` · 9

| line | token | section | cited by |
|---:|---|---|---|
| 85 | BNPD8J3V | Service names | — |
| 184 | BNKPHT1G | Adapter config services | — |
| 195 | BNQKGHGD | Learning services | — |
| 205 | BNTFXJ1X | Setup services (panel-driven) | — |
| 227 | BNV2NJ50 | Mapping services | — |
| 320 | BN0JNMVV | Theme services | — |
| 337 | BN6DJDXS | Internal data keys | — |
| 360 | BN1ENC2F | Events | — |
| 419 | BNTM6TEN | Supported / tested | — |

## `custom_components/eufy_vacuum/core/capabilities.py` · 3

| line | token | section | cited by |
|---:|---|---|---|
| 95 | BNSAZE8S | Entity lookup helpers | — |
| 198 | BN7SHBDE | Maintenance source detection | — |
| 420 | BNWETS61 | Public API | — |

## `custom_components/eufy_vacuum/core/manager.py` · 21

| line | token | section | cited by |
|---:|---|---|---|
| 1019 | BN9Y5WHJ | Callback registration / notification | — |
| 1192 | BNHF6TXT | Vacuum / capability management | — |
| 1409 | BN52YB62 | Water model helpers + estimation -- delegates to RunPlanManager | — |
| 1440 | BNAQ6QDN | Active job tracking — delegates to ActiveJobTracker | — |
| 1649 | BNNH89X5 | Dock actions — delegates to DockManager | — |
| 1990 | BNTXYKSY | Room profiles — delegates to ProfileManager | — |
| 2521 | BN13R22S | Queue / payload building | — |
| 3039 | BNXJC33C | Run profiles — delegates to ProfileManager | — |
| 3072 | BNKAQANF | Access graph — delegates to AccessGraphManager | — |
| 3145 | BN078651 | Run planning -- delegates to RunPlanManager | — |
| 3350 | BNASDHS6 | Room history cache and accessors | — |
| 3703 | BNPN12E3 | Lifecycle / start status | — |
| 4296 | BNA9T0JJ | Singleton-ownership helpers | — |
| 4484 | BN990V7G | Job progress / control | — |
| 4620 | BN5W62XG | Bounds-exit polling signal | — |
| 4723 | BNR8RZFQ | Run anomalies: stall (hard) + running_long (soft) + skipped | — |
| 5735 | BNT7JDBC | Upkeep / maintenance | — |
| 7033 | BNCRE9Z8 | Onboarding — delegates to OnboardingManager | — |
| 7062 | BN9KGAAA | Theme management - delegated to self.themes (ThemeManager) | — |
| 7111 | BN40D32F | Dock events — delegates to DockManager | — |
| 7132 | BN8XKZWY | Job start / run-profile start | — |

## `custom_components/eufy_vacuum/dock/manager.py` · 4

| line | token | section | cited by |
|---:|---|---|---|
| 116 | BN77YS6F | Private helpers | — |
| 241 | BNVV5A75 | Dock action status | — |
| 430 | BN1T5E99 | Dock action dispatch | — |
| 540 | BNYMF7A6 | Dock event recording | — |

## `custom_components/eufy_vacuum/learning/estimator.py` · 17

| line | token | section | cited by |
|---:|---|---|---|
| 129 | BNPZ4HQP | Tunable constants | — |
| 205 | BNKNJ83W | Helpers | — |
| 338 | BNTDS01E | Learning velocity | — |
| 388 | BNNKMW2Y | Confidence scoring | — |
| 438 | BNM44SMY | Overhead modeling | — |
| 544 | BNFGHYVM | Room stat lookup | — |
| 760 | BNZFXXB3 | Main estimator class | — |
| 776 | BNX0VKNC | Stale detection | — |
| 801 | BNZ7NT64 | Accuracy stats | — |
| 1001 | BNEYFJA0 | Core estimate | — |
| 1145 | BN8A2JMG | Per-room estimation | — |
| 1392 | BNV5916D | Overhead | — |
| 1422 | BN04S802 | Job-level confidence — min of all room scores (hard rule) | — |
| 1437 | BNBCR902 | Job ETA | — |
| 1443 | BNGPJPM7 | Battery readiness | — |
| 1503 | BNB7HKSE | Next room shortcut | — |
| 1543 | BNGCS4JP | Timeline reanchoring | — |

## `custom_components/eufy_vacuum/learning/history_store.py` · 2

| line | token | section | cited by |
|---:|---|---|---|
| 666 | BNDGR3XF | Incomplete run log | — |
| 722 | BNWM3ZGR | Trouble rooms log | — |

## `custom_components/eufy_vacuum/learning/job_segmenter_engines.py` · 5

| line | token | section | cited by |
|---:|---|---|---|
| 75 | BN55BATD | Canonical cross-engine contract. | — |
| 130 | BN0PA3DC | Protocol. | — |
| 183 | BNT4BNT4 | Eufy engine — counter-plateau, delegates verbatim. | — |
| 294 | BNJ4K8X5 | Noop fallback — for a future brand with no segmentable signal. | — |
| 342 | BN95SS8Y | Registry. | — |

## `custom_components/eufy_vacuum/learning/room_attribution_engines.py` · 5

| line | token | section | cited by |
|---:|---|---|---|
| 54 | BNBYP2TY | Canonical cross-engine contracts. | — |
| 102 | BN8DV7XK | Protocol. | — |
| 128 | BN5KJ83S | Eufy engine — anchor + winding + swept-area; ports the validated prototype. | — |
| 346 | BNS27NK6 | Noop fallback — for a future brand with no usable pose stream. | — |
| 374 | BNKAY1T5 | Registry. | — |

## `custom_components/eufy_vacuum/learning/services.py` · 2

| line | token | section | cited by |
|---:|---|---|---|
| 803 | BNMXS80A | Load incomplete run log (file I/O → executor). | — |
| 849 | BNGE63K1 | Start cleaning. | — |

## `custom_components/eufy_vacuum/maintenance/manager.py` · 6

| line | token | section | cited by |
|---:|---|---|---|
| 45 | BNBFVSBR | Module-level pure helpers | — |
| 142 | BNXFRB65 | Pure-function status helpers | — |
| 188 | BN6QNPKK | MaintenanceManager | — |
| 203 | BN6NQY5J | Upkeep model metadata + guide helpers | — |
| 386 | BNNYPRQB | Upkeep snapshot | — |
| 931 | BNF7YZZ4 | Maintenance state / reset / remaining | — |

## `custom_components/eufy_vacuum/mapping/map_source_runtime.py` · 3

| line | token | section | cited by |
|---:|---|---|---|
| 48 | BNBK5XRF | Shared: device identity from the public registry. | — |
| 76 | BNNK54NP | Eufy storage backend. | — |
| 919 | BN47Z0PR | Dreame RASTER backend — consume the base integration's decoded MapData object | — |

## `custom_components/eufy_vacuum/mapping/mapping_services.py` · 11

| line | token | section | cited by |
|---:|---|---|---|
| 140 | BNPJAKN9 | Service names | — |
| 182 | BNEDRAMZ | Schemas | — |
| 584 | BN131WEZ | Helpers | — |
| 653 | BN3EPB5V | Polygon math helpers | — |
| 825 | BN6NPMKA | Image analysis handlers | `docs/dev/11-map-stored-state.md` |
| 1578 | BNC3PSH3 | Custom layouts — named collection of no-CV segmentations per map | `docs/dev/11-map-stored-state.md` |
| 2210 | BN436BDT | Furnished custom render (Wave 0) — per-layout furnished-art overlay state | `docs/dev/11-map-stored-state.md` |
| 2628 | BNS7MCWP | Custom layout CRUD | `docs/dev/11-map-stored-state.md` |
| 2772 | BNWZH4DA | Saved-zone CRUD (Wave 1 — storage only; filing + dispatch are later waves) | `docs/dev/11-map-stored-state.md` |
| 3030 | BNCBE0NT | Registration | — |
| 3040 | BNB7AGJH | Image analysis services | — |

## `custom_components/eufy_vacuum/mapping/segmenter_engines.py` · 7

| line | token | section | cited by |
|---:|---|---|---|
| 39 | BN5Z6F7W | Type definitions — the canonical SegmentationResult contract. | — |
| 174 | BN3XPZM4 | Protocol — what the framework registers in _SEGMENTER_ENGINES. | — |
| 211 | BNHJ5AKM | Eufy CV engine — wraps the existing detect_room_segments pipeline. | — |
| 327 | BNH7N8GP | Internal | — |
| 362 | BN4X66AM | Noop fallback — for adapters that yield no segmentation at all. | — |
| 407 | BN5HEHJ2 | Registry | — |
| 451 | BNTWD4V0 | Internal helpers | — |

## `custom_components/eufy_vacuum/mapping/tracker.py` · 7

| line | token | section | cited by |
|---:|---|---|---|
| 45 | BNX0V0H3 | Constants | — |
| 110 | BNJYEYJG | Per-vacuum tracker state | — |
| 167 | BN5D4RKA | Tracker | — |
| 199 | BNFQRJDY | Dock-coordinate drift log (diagnostic) | — |
| 332 | BN7N3R5Z | Listener registration | — |
| 390 | BNEKTDZR | Job lifecycle | — |
| 461 | BNRTVX2S | Position handling | — |

## `custom_components/eufy_vacuum/models/models.py` · 2

| line | token | section | cited by |
|---:|---|---|---|
| 31 | BNVAM19F | Rule models | — |
| 110 | BNDTA35W | Theme models | — |

## `custom_components/eufy_vacuum/onboarding/manager.py` · 2

| line | token | section | cited by |
|---:|---|---|---|
| 65 | BN3BEJTH | Private helpers | — |
| 112 | BNW9AAN5 | Public API | — |

## `custom_components/eufy_vacuum/planning/run_plan.py` · 5

| line | token | section | cited by |
|---:|---|---|---|
| 74 | BN3WEMRE | Module-level pure helpers (duplicated from core/manager.py where also used) | — |
| 244 | BN31DWVA | RunPlanManager | — |
| 256 | BNFFVWNW | Water model helpers | — |
| 393 | BNS19G4Z | Water usage estimation | — |
| 625 | BN6EGRMT | Run planning helpers | — |

## `custom_components/eufy_vacuum/profiles/manager.py` · 3

| line | token | section | cited by |
|---:|---|---|---|
| 123 | BN9M1MVS | ID generators | — |
| 409 | BNW696N6 | Room profile CRUD | — |
| 1045 | BNP8V5FN | Run profile CRUD | — |

## `custom_components/eufy_vacuum/queue/dispatch_engines.py` · 1

| line | token | section | cited by |
|---:|---|---|---|
| 425 | BNBPG3M5 | Registry | — |

## `custom_components/eufy_vacuum/rooms/access_graph.py` · 9

| line | token | section | cited by |
|---:|---|---|---|
| 130 | BN9HSWTX | Internal ID generator | — |
| 139 | BNQHVRGC | Normalization | — |
| 264 | BNB031V0 | Managed rooms with automation metadata | — |
| 305 | BNX8KSJR | Access graph views | — |
| 352 | BNYV5NW7 | Issue formatting | — |
| 529 | BNDK0JMV | Room access context (internal aggregate) | — |
| 601 | BNS70XJJ | Public API — access graph editor / health | — |
| 944 | BNRYWGGQ | Validation | — |
| 1294 | BNX4QZGD | Rule evaluation | — |

## `custom_components/eufy_vacuum/rooms/source_refresh.py` · 3

| line | token | section | cited by |
|---:|---|---|---|
| 181 | BN9RY7DZ | Cache accessors | — |
| 264 | BNAJ69WK | Flatten shim (pure — no hass) | — |
| 438 | BN2YZGWK | Async refresher | — |

## `custom_components/eufy_vacuum/sensor/lifecycle.py` · 3

| line | token | section | cited by |
|---:|---|---|---|
| 76 | BN93905S | HA lifecycle | — |
| 114 | BNK3GSCT | Update callbacks | — |
| 183 | BNCDV51F | State | — |

## `custom_components/eufy_vacuum/setup/workflow.py` · 3

| line | token | section | cited by |
|---:|---|---|---|
| 34 | BN47ST30 | Internal helpers | — |
| 61 | BN3WR8AM | add_vacuum | — |
| 136 | BNR06W9B | import_active_map | — |

## `custom_components/eufy_vacuum/themes/manager.py` · 3

| line | token | section | cited by |
|---:|---|---|---|
| 123 | BNQWR9SP | Callback management | — |
| 149 | BNDN4WKD | Private helpers | — |
| 288 | BNCXHCJ9 | Public API | — |

## `custom_components/eufy_vacuum/themes/preloaded.py` · 3

| line | token | section | cited by |
|---:|---|---|---|
| 14 | BNFMJ978 | Build helpers | — |
| 284 | BN1AX4KE | Base spec and preloaded theme list | — |
| 515 | BN2DJBKT | Library seeder | — |

## `custom_components/eufy_vacuum/themes/services.py` · 3

| line | token | section | cited by |
|---:|---|---|---|
| 57 | BNRSG97G | Schemas | — |
| 139 | BNEA5RRB | Helpers | — |
| 176 | BND8DXX9 | Registration | — |

## `scripts/gen_event_docs.py` · 7

| line | token | section | cited by |
|---:|---|---|---|
| 91 | BNB5542G | blind-spot ledger | — |
| 109 | BNC874K2 | 1. parse the package | — |
| 154 | BNWXRS80 | 2. module-level string constants — INCLUDING f-strings | — |
| 243 | BNQYEQND | 3. function/method index — for resolving builder calls | — |
| 333 | BNTYV3XR | 4. every async_fire call site | — |
| 588 | BNF6JNDQ | 5. the model | — |
| 690 | BNGXW9T3 | 6. emit the reference | — |

## `src/actions/rooms.js` · 4

| line | token | section | cited by |
|---:|---|---|---|
| 75 | BNB9BKM3 | 1) Confirm start status against backend truth | — |
| 96 | BNAXGMHJ | 2) Start selected rooms | — |
| 156 | BNYCFWAT | 3) Run learning estimate and store the full payload | — |
| 174 | BN7WZN6Q | 4) Enter active learning-job mode | — |

## `src/bindings/map.js` · 2

| line | token | section | cited by |
|---:|---|---|---|
| 3005 | BN3KGZJ9 | Double-click on map background → reset transform | — |
| 3015 | BNVMC3YY | Touch pinch zoom | — |

## `src/controllers/learning-controller-progress.test.mjs` · 3

| line | token | section | cited by |
|---:|---|---|---|
| 62 | BNGAA1QF | getRoomProgressSnapshot — BACKEND path | — |
| 179 | BNNZFY5R | getRoomProgressSnapshot — LOCAL timeline path | — |
| 295 | BNADC9QG | computeProgressPercent | — |

## `src/renderers/setup.js` · 2

| line | token | section | cited by |
|---:|---|---|---|
| 68 | BN00X12B | Setup steps wizard | — |
| 958 | BN2P065F | System entity bindings | — |

## `src/state/clean-mode-options.test.mjs` · 1

| line | token | section | cited by |
|---:|---|---|---|
| 109 | BNSW5H06 | Water level: "Off" is not offered while mopping | — |

## `src/state/maintenance-logic.test.mjs` · 2

| line | token | section | cited by |
|---:|---|---|---|
| 28 | BNPM3VTK | findUpkeepItem | — |
| 96 | BNP0PFCA | canInvokeMaintenanceReset | — |

## `src/theme-tokens/floor-scope.test.mjs` · 4

| line | token | section | cited by |
|---:|---|---|---|
| 33 | BN9E1X7P | floorTypeNames / prefixes / keyInType (whole-name, never dash-split) | — |
| 66 | BNP10789 | detectFloorScope — known/unknown partition | — |
| 127 | BNGVX4JV | sliceThemeByTypes — keep only wanted types across the 3 sections | — |
| 200 | BN2CB85J | clampThemeScalars — clamp bounded scalars, pass colors/rangeless through | — |
