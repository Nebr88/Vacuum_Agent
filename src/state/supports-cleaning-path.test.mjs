// Run: node --test src/state/supports-cleaning-path.test.mjs
//
// Coverage targets — the user-owned capability, CARD half
//   [SCP-1] an explicit false is false
//   [SCP-2] an explicit true is true
//   [SCP-3] absent / null is NULL — "not established", NOT false
//   [SCP-4] the renderer hides the picker ONLY on an explicit false
//
// WHY THE THIRD STATE EXISTS. Some brands DERIVE this — Roborock from whether the
// device's own mop-route select carries a usable value — and some GUESSED it. Eufy
// answered with `model_family in {"x10","x8"}`, a conservative stand-in for knowledge
// nobody had gathered. Read as a plain boolean, that guess DENIES the control to
// hardware that may well have it, which is why the flag now belongs to the user and
// why "nobody has established this" has to be representable.
//
// So this accessor deliberately does NOT behave like `supportsEdgeMopping`, which
// collapses the unknown case to true. A caller must test `=== false`.
//
// This is also NOT `supports_path_control`: the backend's dispatcher reads that one as
// GO-TO support ("declares path control (go-to) unsupported"). Two capabilities, two
// names — they were one flag, which is how an unavailable mop-route select came to be
// able to gate go-to.

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyLearningState } from "./learning.js";

function makeState(snapshot) {
  const proto = {};
  applyLearningState(proto);
  const state = Object.create(proto);
  state.dashboardSnapshot = () => snapshot;
  return state;
}

test("[SCP-1] an explicit false is false", () => {
  assert.equal(
    makeState({ supports_cleaning_path: false }).supportsCleaningPath(), false,
  );
});

test("[SCP-2] an explicit true is true", () => {
  assert.equal(
    makeState({ supports_cleaning_path: true }).supportsCleaningPath(), true,
  );
});

test("[SCP-3] absent or null is NULL, not false", () => {
  // The load-bearing case. `=== false` must be false for all of these, or every brand
  // nobody has asked loses the control.
  for (const snapshot of [{}, { supports_cleaning_path: null }, null, undefined]) {
    const v = makeState(snapshot).supportsCleaningPath();
    assert.equal(v, null, `expected null for ${JSON.stringify(snapshot)}`);
    assert.notEqual(v, false, "not-established must not read as an explicit false");
  }
});

test("[SCP-4] the gate fires ONLY on an explicit false", () => {
  // Mirrors `src/renderers/room-editor.js::_renderCleanIntensityField`'s guard.
  const hidden = (v) => v === false;

  assert.equal(hidden(makeState({ supports_cleaning_path: false }).supportsCleaningPath()), true);
  assert.equal(hidden(makeState({ supports_cleaning_path: true }).supportsCleaningPath()), false);
  assert.equal(hidden(makeState({}).supportsCleaningPath()), false,
    "an unasked brand must keep its control");
});
