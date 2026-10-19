// Run: node --test src/state/brand-default-setting.test.mjs
//
// Coverage targets — issue #71 follow-up, the CARD half
//   [BDS-1] a value equal to the brand's declared default is "at default"
//   [BDS-2] a value that differs is not — case-insensitively, both ways
//   [BDS-3] an empty value is at default (nothing was chosen, nothing to show)
//   [BDS-4] NO declaration => NOT default, so an unknown brand shows every chip
//           rather than silently hiding settings the user did pick
//   [BDS-5] each axis is answered independently
//   [BDS-6] the three brands' real defaults, as the backend derives them
//
// The Rooms view hides a setting chip whose value is the default. It decided that
// with brand WORDS hardcoded in a brand-agnostic renderer:
//
//     isDefaultPower = !fanSpeed || ["off","normal"].includes(fanSpeed)
//     isDefaultPath  = !cleanIntensity || cleanIntensity === "standard"
//
// Neither suction word exists in ANY shipped brand's vocabulary — Eufy says
// Quiet/Standard/Turbo/Max, Roborock quiet/balanced/turbo/max/gentle, Dreame
// quiet/standard/strong/turbo — so that test NEVER FIRED and the suction chip
// rendered on every room including the defaults it was written to hide. `"normal"`
// is the tell: `vocab.clean_intensity.normal` exists and is marked manual-only, so
// the pair reads as copied out of an intensity context into a fan test.
//
// The path word was right for Roborock and Dreame by coincidence (both default to
// `standard`) and wrong for Eufy, where `standard` is a RETIRED clean_intensity
// value — so it hid a value that should not exist and showed the real default.
//
// That is f/eufy_is_not_the_default inside a renderer: core owns the KEY, never the
// brand's word. The brand already states this, in the profile `default_profile`
// names, and the backend now ships it as `room_setting_defaults`.

import { test } from "node:test";
import assert from "node:assert/strict";

import { applyLearningState } from "./learning.js";

function makeState(defaults) {
  const proto = {};
  applyLearningState(proto);
  const state = Object.create(proto);
  state.dashboardSnapshot = () =>
    defaults === undefined ? {} : { room_setting_defaults: defaults };
  return state;
}

// The real values, as `default_setting_values()` derives them from each brand's
// `default_profile`. Roborock's `path_type` is folded onto the canonical name.
const EUFY = { fan_speed: "Standard", clean_intensity: "Quick", water_level: "Off" };
const ROBOROCK = { fan_speed: "balanced", clean_intensity: "standard", water_level: "off" };
const DREAME = { fan_speed: "standard", clean_intensity: "standard" };

test("[BDS-1] a value equal to the brand's default is at default", () => {
  const state = makeState(ROBOROCK);
  assert.equal(state.isBrandDefaultSetting("fan_speed", "balanced"), true);
  assert.equal(state.isBrandDefaultSetting("clean_intensity", "standard"), true);
});

test("[BDS-2] a different value is not, and case does not decide it", () => {
  const state = makeState(EUFY);
  assert.equal(state.isBrandDefaultSetting("fan_speed", "Max"), false);
  // Eufy stores display-cased words; a brand could declare either casing.
  assert.equal(state.isBrandDefaultSetting("fan_speed", "standard"), true);
  assert.equal(state.isBrandDefaultSetting("fan_speed", "  STANDARD  "), true);
});

test("[BDS-3] an empty value is at default — nothing chosen, nothing to show", () => {
  const state = makeState(ROBOROCK);
  for (const empty of ["", "   ", null, undefined]) {
    assert.equal(state.isBrandDefaultSetting("fan_speed", empty), true);
  }
});

test("[BDS-4] no declaration => NOT default, so nothing is hidden silently", () => {
  // The failure direction matters. Treating "no declaration" as default would hide
  // settings a user deliberately chose, on exactly the brands we know least about.
  for (const snapshot of [undefined, {}, { fan_speed: "" }]) {
    const state = makeState(snapshot);
    assert.equal(state.isBrandDefaultSetting("fan_speed", "turbo"), false);
  }
});

test("[BDS-5] axes are answered independently", () => {
  const state = makeState(ROBOROCK);
  // `standard` IS Roborock's default path and is NOT its default suction.
  assert.equal(state.isBrandDefaultSetting("clean_intensity", "standard"), true);
  assert.equal(state.isBrandDefaultSetting("fan_speed", "standard"), false);
});

test("[BDS-6] the retired literals no longer decide anything", () => {
  // The words the renderer used to hardcode, against each brand's real defaults.
  for (const [name, defaults] of [["eufy", EUFY], ["roborock", ROBOROCK], ["dreame", DREAME]]) {
    const state = makeState(defaults);
    assert.equal(
      state.isBrandDefaultSetting("fan_speed", "normal"), false,
      `${name}: "normal" is in no brand's fan vocabulary and must decide nothing`,
    );
  }

  // And the path word, which was right twice by luck and wrong once.
  assert.equal(makeState(EUFY).isBrandDefaultSetting("clean_intensity", "standard"), false,
    "Eufy's default is Quick; `standard` is a RETIRED value and must not read as default");
  assert.equal(makeState(EUFY).isBrandDefaultSetting("clean_intensity", "Quick"), true);
  assert.equal(makeState(ROBOROCK).isBrandDefaultSetting("clean_intensity", "standard"), true);
  assert.equal(makeState(DREAME).isBrandDefaultSetting("clean_intensity", "standard"), true);
});
