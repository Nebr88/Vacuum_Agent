"""The mop ladder read off the device instead of declared (issue #71).

`WATER_LEVEL_OPTIONS` was a transcript of ONE machine — the maintainer's S6, which
offers off/low/medium/high — applied to every Roborock. Measured on the reporter's
Saros 10 (a147): the same select offers `off / mild / standard / intense / extreme /
smart_mode / custom`, and **not one of low, medium, high exists there**. The global
water pre-call was pushing three words that mop rejects, and because water is a
best-effort entry it failed into the log on every run while the robot kept whatever the
vendor app had set.

WHY THE READ IS SAFE WHERE THE ROUTE GATE WAS NOT. `_route_usable` needs a usable
STATE, and the S6's mop_mode never leaves `unavailable`. `options` is an ATTRIBUTE,
published with the entity regardless of state — verified live: `select.ivy_mop_intensity`
sits at `unknown` and still carries off/low/medium/high. LW-9 pins that difference,
because reusing the route gate's state test here would read nothing on exactly the
hardware that proved the route gate necessary.

WHAT THESE TESTS GUARD is mostly the shoulders. The happy path is one attribute read.
The ways it goes wrong are: ranking a non-rung (§E2 — an unrankable value makes
`_any_rankable` False and the safest-water push silently does nothing, issue #51's
wet-mop reopened); deriving picker and rank separately so they drift apart; and
producing an EMPTY list, which §E1 says disables the guard rather than tightening it.

Coverage targets
----------------
[LW-1]  the Saros shape: the device's five rungs become the picker AND the rank.
[LW-2]  a device publishing our declared ladder is unchanged — the no-regression guard.
[LW-3]  no entity at all -> the declared list, never an empty vocabulary.
[LW-4]  entity present, no `options` attribute -> the declared list.
[LW-5]  options that are ALL non-rungs -> the declared list, NOT an empty one (§E1).
[LW-6]  picker and rank are the same sequence — they are a replica pair.
[LW-7]  a token nobody has a word for is humanised, not left raw.
[LW-8]  a declared label beats humanisation (`deep_plus` -> "Deep+", not "Deep Plus").
[LW-9]  an `unknown` state still yields options — the ivy case, and the whole point.
[LW-10] blanks and duplicates from the device are dropped.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import (
    clear_registry,
    get_adapter_config,
)
from custom_components.eufy_vacuum.adapters.roborock import adapter as rb
from custom_components.eufy_vacuum.adapters.roborock import vocabulary as rbv
from custom_components.eufy_vacuum.adapters.roborock.entities import build_entity_id

_RVAC = "vacuum.ivy"

#: Pasted unmodified from the reporter's Developer Tools, issue #71 (2026-10-19).
SAROS_MOP_INTENSITY = ["off", "mild", "standard", "intense", "extreme", "smart_mode", "custom"]

#: The maintainer's S6, read live off the box the declared list was transcribed from.
S6_MOP_INTENSITY = ["off", "low", "medium", "high"]


class _FakeDevice:
    def __init__(self, manufacturer, model):
        self.manufacturer = manufacturer
        self.model = model


def _register(monkeypatch, hass, *, options=None, state="unknown", model="roborock.vacuum.zz99"):
    """Register the adapter for a MOP-SETTABLE model, optionally publishing the select.

    An uncatalogued model takes DEFAULT_PROFILE's optimistic `mop_settable: True`, but
    issue #67 narrows that to "a mop module is CLAIMED" — and the claim is the water-box
    binary sensor, which upstream gates on `is_support_water_mode`. Without it the
    adapter treats the device as mopless and declares no water axis at all, so this
    fixture publishes it. The reporter's Saros 10 has one; that is why it gets a water
    pre-call and why it was being pushed words its mop rejects.
    """
    clear_registry()
    monkeypatch.setattr(rb, "_device_for_vacuum", lambda h, v: _FakeDevice("Roborock", model))
    hass.states.async_set(_RVAC, "cleaning", {"supported_features": 30524, "fan_speed": "max"})
    hass.states.async_set(build_entity_id(_RVAC, "_water_box_attached", "binary_sensor"), "on")
    if options is not None:
        hass.states.async_set(
            build_entity_id(_RVAC, "_mop_intensity", "select"), state, {"options": options}
        )
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    return get_adapter_config(_RVAC)


def _water_pre_call(cfg):
    for entry in (cfg.get("dispatch") or {}).get("global_pre_calls") or []:
        if entry.get("field") == "water_level":
            return entry
    return None


def _values(cfg):
    return [o["value"] for o in cfg["vocabulary"]["water_level_options"]]


_DECLARED_VALUES = [str(o["value"]) for o in rbv.WATER_LEVEL_OPTIONS]


# ---------------------------------------------------------------------------
# The read
# ---------------------------------------------------------------------------

def test_lw_1_the_saros_ladder_becomes_the_picker_and_the_rank(monkeypatch, hass):
    """[LW-1] The reporter's device, with their own tokens.

    The two non-rungs must not survive into either list: `smart_mode` means "the robot
    decides" and `custom` means "whatever the app last set". Neither is a position on a
    ladder, and ranking one is §E2.
    """
    cfg = _register(monkeypatch, hass, options=SAROS_MOP_INTENSITY)

    assert _values(cfg) == ["off", "mild", "standard", "intense", "extreme"]
    assert _water_pre_call(cfg)["rank"] == ["off", "mild", "standard", "intense", "extreme"]
    # The words we used to push do not exist on this machine — that was the defect.
    assert not {"low", "medium", "high"} & set(_values(cfg))


def test_lw_2_a_device_publishing_our_declared_ladder_is_unchanged(monkeypatch, hass):
    """[LW-2] THE NO-REGRESSION GUARD. A device whose ladder matches what we declared
    must come through byte-identical, or the fix is a change of behaviour for every
    existing Roborock rather than a repair for one."""
    cfg = _register(monkeypatch, hass, options=S6_MOP_INTENSITY)

    assert _values(cfg) == _DECLARED_VALUES
    assert cfg["vocabulary"]["water_level_options"] == list(rbv.WATER_LEVEL_OPTIONS)
    assert _water_pre_call(cfg)["rank"] == _DECLARED_VALUES


def test_lw_9_an_unknown_state_still_yields_options(monkeypatch, hass):
    """[LW-9] The ivy case, and the reason this is not `_route_usable`.

    `select.ivy_mop_intensity` sits at `unknown` forever — the S6's mop is observe-only.
    Its `options` attribute is published anyway. Had this reused the route gate's
    usable-VALUE test, it would read nothing on precisely the hardware that proved the
    route gate was needed.

    ABLATION: gate the read on the state like `_route_usable` does and this goes red
    while LW-1 stays green — the same asymmetry that let the route bug through.
    """
    cfg = _register(monkeypatch, hass, options=SAROS_MOP_INTENSITY, state="unknown")
    assert _values(cfg) == ["off", "mild", "standard", "intense", "extreme"]

    cfg = _register(monkeypatch, hass, options=SAROS_MOP_INTENSITY, state="unavailable")
    assert _values(cfg) == ["off", "mild", "standard", "intense", "extreme"]


# ---------------------------------------------------------------------------
# The fallbacks — every one of these must land on the DECLARED list, never []
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "options,why",
    [
        (None, "[LW-3] the provider integration has not set up yet"),
        ([], "[LW-4] the entity exists but published no options"),
        (["smart_mode", "custom"], "[LW-5] every option it published is a non-rung"),
        (["", "   "], "[LW-5] every option it published is blank"),
    ],
)
def test_lw_3_4_5_every_empty_read_falls_back_to_the_declaration(
    monkeypatch, hass, options, why
):
    """[LW-3][LW-4][LW-5] An empty derived list must never reach the config.

    §E1: an empty options list DISABLES the fan/water guard rather than tightening it
    (`if valid and ...`), so "we read nothing" must mean "use what we declared", never
    "the device has no water axis". The cold-boot window where the provider has not set
    up is the common case and is exactly when a wrong answer would latch into a config.
    """
    cfg = _register(monkeypatch, hass, options=options)

    assert cfg["vocabulary"]["water_level_options"] == list(rbv.WATER_LEVEL_OPTIONS), why
    assert _water_pre_call(cfg)["rank"] == _DECLARED_VALUES, why


# ---------------------------------------------------------------------------
# The invariants
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "options", [SAROS_MOP_INTENSITY, S6_MOP_INTENSITY, None, ["off", "wibble", "custom"]]
)
def test_lw_6_the_picker_and_the_rank_are_one_sequence(monkeypatch, hass, options):
    """[LW-6] They are a replica pair, and the failure is SILENT.

    A value the picker offers that the rank does not know makes `_any_rankable` False,
    and the safest-water pre-call then pushes NOTHING — the batch proceeds on whatever
    water the vendor app last set (§E2 / issue #51). No error, no log, a wet floor. The
    only defence is that there is one derivation, so this asserts identity rather than
    equality-of-contents for every shape the read can produce.
    """
    cfg = _register(monkeypatch, hass, options=options)
    assert _water_pre_call(cfg)["rank"] == _values(cfg)


def test_lw_10_blanks_and_duplicates_from_the_device_are_dropped(monkeypatch, hass):
    """[LW-10] The device is not a trusted producer of a clean list."""
    cfg = _register(monkeypatch, hass, options=["off", "", "mild", "off", "  ", "mild"])
    assert _values(cfg) == ["off", "mild"]


# ---------------------------------------------------------------------------
# Labels — the open-set problem
# ---------------------------------------------------------------------------

def test_lw_7_a_token_nobody_has_a_word_for_is_humanised(monkeypatch, hass):
    """[LW-7] The set of words a Roborock can emit is NOT knowable, so no table can
    cover it — a firmware update adds a rung and we must not put a raw token on the card.

    The card resolves `vocab.<field>.<value>` first and falls back to the backend label
    (`src/i18n/en.js`:120), so an untranslated rung degrades to readable English instead
    of breaking. That is what makes the live read shippable without 18 language packs.
    """
    assert rbv.humanize_option("off_raise_main_brush") == "Off Raise Main Brush"
    assert rbv.humanize_option("max_plus") == "Max Plus"

    cfg = _register(monkeypatch, hass, options=["off", "extreme", "zz_new_rung"])
    labels = {o["value"]: o["label"] for o in cfg["vocabulary"]["water_level_options"]}
    assert labels["extreme"] == "Extreme"
    assert labels["zz_new_rung"] == "Zz New Rung"


def test_lw_8_a_declared_label_beats_humanisation():
    """[LW-8] Mechanical title-casing is the FALLBACK, not the rule. `deep_plus` is the
    case that proves it: humanising gives "Deep Plus", and the adapter's own word is
    "Deep+". A test using a token whose two spellings agree would pass either way."""
    assert rbv.humanize_option("deep_plus") == "Deep Plus"
    assert rbv.build_option_list(["deep_plus"]) == [{"value": "deep_plus", "label": "Deep+"}]


def test_lw_11_the_profiles_are_retuned_to_the_devices_ladder(monkeypatch, hass):
    """[LW-11] THE SECOND WRITER. Repairing stored rooms is not enough.

    Both Roborock mop profiles declare ``water_level: "medium"`` — canonical, present
    on an S6, and ABSENT on a Saros whose ladder is off/mild/standard/intense/extreme.
    ``apply_room_profile_to_config`` writes the profile's value straight onto the room,
    so a user applying "Quick" AFTER the one-shot repair had run would put the retired
    word back. The dispatch filter drops it, the safest-water pre-call then finds
    nothing rankable and pushes nothing, and the batch runs on whatever the vendor app
    last set — issue #51's wet-mop, reachable by pressing a button the card offers.

    Found by the pre-release audit. The repair and the declaration must agree, so the
    same positional alias map is applied to both.
    """
    cfg = _register(monkeypatch, hass, options=SAROS_MOP_INTENSITY)

    allowed = {o["value"] for o in cfg["vocabulary"]["water_level_options"]}
    profiles = cfg["room_profiles"]["builtins"]
    assert profiles, "no profiles declared — this test would pass vacuously"

    for name, profile in profiles.items():
        water = profile.get("water_level")
        if water in (None, ""):
            continue
        assert water in allowed, (
            f"profile {name!r} declares water_level={water!r}, which this device "
            "does not offer — applying it re-introduces an out-of-vocabulary value"
        )
    # The canonical middle rung became the device's middle rung, not something else.
    assert profiles["vacuum_mop_quick"]["water_level"] == "standard"
    assert cfg["room_profiles"]["custom_template"]["water_level"] in allowed


def test_lw_12_an_unchanged_ladder_leaves_the_profiles_untouched(monkeypatch, hass):
    """[LW-12] The S6 case: the device publishes the ladder we declared, so there are
    no aliases and the profiles must come through byte-identical. Without this, LW-11
    could be satisfied by rewriting profiles on every brand and every model."""
    cfg = _register(monkeypatch, hass, options=S6_MOP_INTENSITY)

    assert cfg["room_profiles"]["builtins"]["vacuum_mop_quick"]["water_level"] == "medium"
    assert cfg["room_profiles"]["builtins"] is rbv.ROOM_PROFILES, (
        "retuned a profile set that did not need it"
    )
