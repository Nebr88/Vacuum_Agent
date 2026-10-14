// Run: node --test src/bindings/setup-adopt-room.test.mjs
//
// ISSUE #70 — Add room must REUSE the import, not become a second write path.
//
// `import_active_map` already calls save_managed_rooms(enabled_room_ids=None) — include
// every discovered room — and build_managed_rooms preserves existing per-room settings
// for rooms still discovered. So adoption is the tested route with a button on it. A
// bespoke "adopt one room" write would be a second path to the same store, diverging
// from the first the moment either changed.
//
// Coverage (SAB = Setup Adopt Binding):
//   [SAB-1] Add room fires importActiveMap and re-polls status
//   [SAB-2] it does NOT call save/reject — no second write path
//   [SAB-3] a failure surfaces through the setup error channel and clears loading

import { test } from "node:test";
import assert from "node:assert/strict";

import { applySetupBindings } from "./setup.js";

const VAC = "vacuum.alfred";

function makeBinder({ importImpl = null } = {}) {
  const proto = {};
  applySetupBindings(proto);
  const binder = Object.create(proto);

  const registered = {};
  const calls = { import: [], status: [], save: [], reject: [], error: [], loading: [] };

  binder.t = (key, vars) => (vars ? `${key}|${JSON.stringify(vars)}` : key);
  binder.tRaw = (key, vars) => (vars ? `${key}|${JSON.stringify(vars)}` : key);

  binder.card = {
    _config: { vacuum_entity_id: VAC },
    _onAll: (selector, event, handler) => { registered[`${selector}:${event}`] = handler; },
    _scheduleRender: () => {},
    showToast: () => {},
    _state: {
      setSetupLoading: (v) => calls.loading.push(v),
      setSetupError: (v) => { if (v) calls.error.push(v); },
      setSetupLastResult: () => {},
      setSetupStatus: () => {},
      setupStatus: () => ({ vacuums: [] }),
    },
    _actions: {
      importActiveMap: async (vid) => {
        calls.import.push(vid);
        if (importImpl) return importImpl();
        return { status: "success" };
      },
      getSetupStatus: async () => { calls.status.push(1); return { vacuums: [] }; },
      saveSetupRooms: async (...a) => { calls.save.push(a); },
      rejectSetupRooms: async (...a) => { calls.reject.push(a); },
    },
  };

  binder.applySetupBindings?.();
  if (typeof binder.bindSetupEvents === "function") binder.bindSetupEvents();
  else {
    for (const name of Object.getOwnPropertyNames(proto)) {
      if (/^bind.*Setup|^_bindSetup/i.test(name) && typeof binder[name] === "function") binder[name]();
    }
  }

  const fireAdopt = async (roomId) => {
    const handler = registered["[data-action='setup-adopt-room']:click"];
    assert.ok(handler, "the setup-adopt-room click handler was never registered");
    await handler({ currentTarget: { dataset: { roomId: String(roomId) } } });
  };

  return { fireAdopt, calls };
}

test("[SAB-1] Add room fires importActiveMap and re-polls the status", async () => {
  const { fireAdopt, calls } = makeBinder();
  await fireAdopt(7);

  assert.deepEqual(calls.import, [VAC], "adoption did not go through the import path");
  assert.equal(calls.status.length, 1, "the panel would keep showing the room as undiscovered");
});

test("[SAB-2] it opens no second write path", async () => {
  const { fireAdopt, calls } = makeBinder();
  await fireAdopt(7);

  assert.deepEqual(calls.save, [], "a bespoke save would diverge from import's own adoption rules");
  assert.deepEqual(calls.reject, [], "adoption must never reach the reject service");
});

test("[SAB-3] a failed import surfaces and clears loading", async () => {
  const { fireAdopt, calls } = makeBinder({
    importImpl: () => { throw new Error("boom"); },
  });
  await fireAdopt(7);

  assert.equal(calls.error.length, 1, "the failure was swallowed");
  assert.match(calls.error[0], /failed_adopt_room/);
  assert.deepEqual(calls.loading, [true, false], "loading must clear on the failure path");
});
