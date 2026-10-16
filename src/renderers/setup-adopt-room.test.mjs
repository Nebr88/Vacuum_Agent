// Run: node --test src/renderers/setup-adopt-room.test.mjs
//
// ISSUE #70 — a newly discovered room had one button, and it called the room a phantom.
//
// fhteagle split a room in the Eufy app. Vacuum Agent found it, listed it under "new
// rooms discovered", and offered "Reject as phantom" and nothing else. The panel's own
// hint said "Configure the matching map to include them" — and that panel is drawn
// INSIDE the Configure rooms step, whose editor lists MANAGED rooms, so a never-managed
// room can never appear there however fresh discovery is. The instruction pointed at the
// one step structurally unable to carry it out.
//
// Coverage (SA = Setup Adopt):
//   [SA-1] a new room on the ACTIVE map offers Add room
//   [SA-2] a new room on any OTHER map explains why instead of offering a dead button
//   [SA-3] Reject survives in both — Add is an addition, not a replacement
//
// ⚠ THE FIXTURE BELOW IS A CONTRACT, NOT A CONVENIENCE. These tests pass a drift row
// carrying a real `map_id`, and the first version of this file INVENTED that: the
// backend's `_enrich` fell back to `map_id: ""` for any room not in managed storage —
// which is every room `new_rooms` ever contains. So the button never rendered for the
// case it exists for, and this suite could not see it, because the fixture encoded the
// assumption instead of testing it. `[DR-NEW-1]` in tests/integration/test_setup_drift.py
// is what now holds up this shape; change one and the other is wrong.

import { test } from "node:test";
import assert from "node:assert/strict";

import { applySetupRenderers } from "./setup.js";

const VAC = "vacuum.alfred";

function makeHost() {
  const proto = {};
  applySetupRenderers(proto);
  const host = Object.create(proto);
  host.t = (key, vars) => `T:${key}${vars ? `:${JSON.stringify(vars)}` : ""}`;
  host.tRaw = (key, vars) => `RAW:${key}${vars ? `:${JSON.stringify(vars)}` : ""}`;
  host.escapeHtml = (s) => String(s ?? "");
  return host;
}

function render(host, { activeMapId, newRoomMapId }) {
  const status = {
    setup_complete: true,
    vacuums: [
      {
        vacuum_entity_id: VAC,
        display_name: "Alfred",
        setup_steps: [
          { id: "add_vacuum", label: "Add vacuum", completed: true, service: "" },
          { id: "save_rooms", label: "Configure rooms", completed: true, service: "" },
        ],
        next_step: null,
        active_map_id: activeMapId,
        room_drift: {
          in_sync: false,
          new_rooms: [{ room_id: 7, name: "Study", map_id: newRoomMapId }],
          removed_rooms: [],
          transiently_missing: [],
          rejected_rooms: [],
        },
        reconciliation: null,
        maps: [{ map_id: "1", display_name: "Main", room_count: 2, imported: true, protection: null }],
        has_imported_map: true,
      },
    ],
  };
  const state = {
    setupStatus: () => status,
    setupReconcileResolvedToken: () => null,
    setupReconcileResult: () => null,
    setupReconcileRefreshFailed: () => false,
  };
  return host.renderSetupView({ state, card: { _config: { vacuum_entity_id: VAC }, _hass: null } });
}

test("[SA-1] a new room on the ACTIVE map offers Add room", () => {
  const html = render(makeHost(), { activeMapId: "1", newRoomMapId: "1" });

  assert.match(html, /data-action="setup-adopt-room"/, "no way to accept a real new room");
  assert.match(html, /data-room-id="7"/);
  assert.match(html, /T:setup\.adopt_room/);
  assert.doesNotMatch(html, /T:setup\.adopt_needs_active_map/);
});

test("[SA-2] a new room on another map explains instead of offering a dead button", () => {
  // `import_active_map` takes no map id — upstream cannot import a map that is not
  // currently active on the device. A button here would be a no-op dressed as an action.
  const html = render(makeHost(), { activeMapId: "1", newRoomMapId: "2" });

  assert.doesNotMatch(html, /data-action="setup-adopt-room"/,
    "offered adoption for a map the upstream API cannot import");
  assert.match(html, /T:setup\.adopt_needs_active_map/, "silently dropped the button with no explanation");
});

test("[SA-2b] an unknown active map is not assumed to match", () => {
  // active_map_id absent (older backend, or the id could not be resolved). Guessing
  // "probably the same map" would put the dead button back on every row.
  const html = render(makeHost(), { activeMapId: null, newRoomMapId: "1" });

  assert.doesNotMatch(html, /data-action="setup-adopt-room"/);
  assert.match(html, /T:setup\.adopt_needs_active_map/);
});

test("[SA-3] Reject survives in both branches", () => {
  for (const newRoomMapId of ["1", "2"]) {
    const html = render(makeHost(), { activeMapId: "1", newRoomMapId });
    assert.match(html, /data-action="setup-reject-room"/,
      `Reject disappeared when the new room was on map ${newRoomMapId}`);
  }
});
