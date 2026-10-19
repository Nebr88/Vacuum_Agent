"""Suction read off the vacuum entity instead of declared (issue #71, third complaint).

> "For vacuum, there is a MAX+ suction power mode beyond MAX. MAX+ is currently
> missing."

It was missing because `FAN_SPEED_OPTIONS` is a transcript of the maintainer's S6 —
which has `gentle` and no `max_plus` — declared for every Roborock. The reporter's
Saros 10 publishes `quiet, balanced, turbo, max, max_plus, off_raise_main_brush,
smart_mode, custom`: it has neither `gentle` nor our spelling of that slot. Both halves
of the mismatch disappear by asking the device.

WHY THIS IS THE EASY HALF, and it is worth saying because the water read was not.
`fan_speed` is a `per_room_live_settings` entry filtered by `options_key`, NOT a ranked
global pre-call. Nothing orders it, so the `off_raise_main_brush`-is-listed-sixth trap
that makes read-order-as-rank unsafe simply does not apply — here the order is chip
display order, and the device's own order is the one the owner already sees in the
Roborock integration's fan menu. FLR-5 pins that no rank was invented along the way,
because inventing one is the only way to get this wrong.

Coverage targets
----------------
[FLR-1] the Saros list, from the reporter's own tokens, becomes the picker — `max_plus`
        included, `gentle` gone.
[FLR-2] the no-regression guard: a device publishing our declared list is unchanged.
[FLR-3] no entity / no attribute -> the declared list, never an empty one.
[FLR-4] the device's own ORDER is preserved — it is the surface they compared against.
[FLR-5] no rank is introduced; `fan_speed` stays an options_key-filtered per-room entry.
[FLR-6] an unknown rung is humanised, not left raw.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import (
    clear_registry,
    get_adapter_config,
)
from custom_components.eufy_vacuum.adapters.roborock import adapter as rb
from custom_components.eufy_vacuum.adapters.roborock import vocabulary as rbv

_RVAC = "vacuum.saros"

#: Pasted unmodified from the reporter's Developer Tools, issue #71 (2026-10-19).
SAROS_FAN = [
    "quiet", "balanced", "turbo", "max", "max_plus",
    "off_raise_main_brush", "smart_mode", "custom",
]

#: `vacuum.ivy`, read live off the box the declared list was transcribed from.
S6_FAN = ["quiet", "balanced", "turbo", "max", "gentle"]

_DECLARED = [str(o["value"]) for o in rbv.FAN_SPEED_OPTIONS]


class _FakeDevice:
    def __init__(self, manufacturer, model):
        self.manufacturer = manufacturer
        self.model = model


def _register(monkeypatch, hass, *, fan_list=None, model="roborock.vacuum.zz99"):
    clear_registry()
    monkeypatch.setattr(rb, "_device_for_vacuum", lambda h, v: _FakeDevice("Roborock", model))
    attrs = {"supported_features": 30524, "fan_speed": "max"}
    if fan_list is not None:
        attrs["fan_speed_list"] = fan_list
    hass.states.async_set(_RVAC, "cleaning", attrs)
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    return get_adapter_config(_RVAC)


def _values(cfg):
    return [o["value"] for o in cfg["vocabulary"]["fan_speed_options"]]


def test_flr_1_the_saros_list_becomes_the_picker(monkeypatch, hass):
    """[FLR-1] The reported complaint, with their tokens. `max_plus` arrives and
    `gentle` — which that machine does not have — leaves."""
    cfg = _register(monkeypatch, hass, fan_list=SAROS_FAN)

    assert "max_plus" in _values(cfg)
    assert "gentle" not in _values(cfg)
    assert "off_raise_main_brush" in _values(cfg)
    # The two non-rungs are dropped by the shared builder, same as water.
    assert not {"smart_mode", "custom"} & set(_values(cfg))


def test_flr_2_a_device_publishing_our_declared_list_is_unchanged(monkeypatch, hass):
    """[FLR-2] THE NO-REGRESSION GUARD. The S6's own list contains exactly the five we
    declared, so that machine must come through with the same five — a different ORDER
    is fine and expected, since the declaration was never ordered by the device."""
    cfg = _register(monkeypatch, hass, fan_list=S6_FAN)

    assert set(_values(cfg)) == set(_DECLARED)


@pytest.mark.parametrize("fan_list", [None, [], ["smart_mode", "custom"]])
def test_flr_3_an_empty_read_falls_back_to_the_declaration(monkeypatch, hass, fan_list):
    """[FLR-3] Same §E1 rule as water: an empty list would DISABLE the `options_key`
    filter rather than tighten it, so "we read nothing" must mean "use what we
    declared"."""
    cfg = _register(monkeypatch, hass, fan_list=fan_list)

    assert cfg["vocabulary"]["fan_speed_options"] == list(rbv.FAN_SPEED_OPTIONS)


def test_flr_4_the_devices_own_order_is_preserved(monkeypatch, hass):
    """[FLR-4] Not sorted, not re-ranked. The owner compared our picker against the
    Roborock integration's fan menu, which renders this order; matching it is what makes
    the two legible side by side. It is also the only honest order — we do not know
    where a rung we have never seen belongs."""
    cfg = _register(monkeypatch, hass, fan_list=SAROS_FAN)

    assert _values(cfg) == [
        "quiet", "balanced", "turbo", "max", "max_plus", "off_raise_main_brush",
    ]


def test_flr_5_no_rank_is_introduced_for_fan(monkeypatch, hass):
    """[FLR-5] THE TRAP THIS AXIS MUST NOT FALL INTO.

    `off_raise_main_brush` is the WEAKEST rung and the device lists it sixth. Any
    max-wins or safest-wins resolve built on read order would make the raised brush the
    strongest suction. Fan is safe only because it is an `options_key`-filtered
    per-room entry with no rank at all — so this asserts the absence, which is the
    thing a future change would quietly take away.
    """
    cfg = _register(monkeypatch, hass, fan_list=SAROS_FAN)

    per_room = (cfg.get("dispatch") or {}).get("per_room_live_settings") or []
    fan_entries = [e for e in per_room if e.get("field") == "fan_speed"]
    assert len(fan_entries) == 1
    assert "rank" not in fan_entries[0], (
        "a rank over the device's read order would rank off_raise_main_brush highest"
    )
    assert fan_entries[0]["options_key"] == "fan_speed_options"

    pre_calls = (cfg.get("dispatch") or {}).get("global_pre_calls") or []
    assert not [e for e in pre_calls if e.get("field") == "fan_speed"]


def test_flr_6_an_unknown_rung_is_humanised(monkeypatch, hass):
    """[FLR-6] The open set again: a firmware update adds a rung and no table had it."""
    cfg = _register(monkeypatch, hass, fan_list=["quiet", "max_plus", "zz_future"])
    labels = {o["value"]: o["label"] for o in cfg["vocabulary"]["fan_speed_options"]}

    assert labels["max_plus"] == "Max Plus"
    assert labels["zz_future"] == "Zz Future"
    assert labels["quiet"] == "Quiet"  # declared label still wins
