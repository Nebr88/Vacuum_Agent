"""Naming the live reads that came back empty, so core can come back for them.

EXISTING ENTITIES ARE NOT PUBLISHED ENTITIES, and the whole live-vocabulary feature
lands in the gap between the two. `async_at_started` guarantees every integration has
SET UP — enough to ask whether an entity exists — but an adapter reading an entity's
ATTRIBUTES needs the provider's coordinator to have POLLED.

Measured on the maintainer's box and this is the only reason the gap was found: 150
seconds after a restart the registered adapter still held the DECLARED suction list,
while `vacuum.ivy` was plainly publishing `fan_speed_list` to anyone who asked. A
config-entry reload immediately produced the device's own lists. So on every restart a
user would have got the old wrong vocabulary — the Saros 10 owner of issue #71 would
have seen the fix silently not apply, with `low`/`medium`/`high` still being pushed at a
mop that rejects them.

The fallback is safe and wrong: safe because a declared list is always a valid list,
wrong because reading the device is the entire point. So the adapter NAMES the entities
whose read came back empty and core watches them. Reporting an id costs nothing if it
never publishes; an install where everything published on time arms no listener at all.

Coverage targets
----------------
[VCU-1] nothing published -> every unread source is named.
[VCU-2] everything published -> NOTHING is named, so no listener is armed.
[VCU-3] a partial read names only the sources still missing.
[VCU-4] the water select is not named on a model whose mop is not settable — there is
        no water vocabulary to wait for, so waiting would never end.
[VCU-5] the names are real entity ids the state machine can be watched on, not object
        ids — a wrong id would wait forever and look exactly like a device that never
        publishes.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import (
    clear_registry,
    get_adapter_config,
)
from custom_components.eufy_vacuum.adapters.roborock import adapter as rb

_RVAC = "vacuum.ivy"

_SAROS_FAN = ["quiet", "balanced", "turbo", "max", "max_plus"]
_SAROS_ROUTE = ["standard", "deep", "deep_plus", "fast"]
_SAROS_WATER = ["off", "mild", "standard", "intense", "extreme"]


class _FakeDevice:
    def __init__(self, manufacturer, model):
        self.manufacturer = manufacturer
        self.model = model


def _register(monkeypatch, hass, *, fan=None, route=None, water=None,
              model="roborock.vacuum.zz99", mop=True):
    clear_registry()
    monkeypatch.setattr(rb, "_device_for_vacuum", lambda h, v: _FakeDevice("Roborock", model))
    attrs = {"supported_features": 30524, "fan_speed": "max"}
    if fan is not None:
        attrs["fan_speed_list"] = fan
    hass.states.async_set(_RVAC, "cleaning", attrs)
    if mop:
        # The water-box sensor is what claims a mop module (#67); without it the
        # adapter treats an uncatalogued model as mopless and declares no water axis.
        hass.states.async_set("binary_sensor.ivy_water_box_attached", "on")
    if route is not None:
        hass.states.async_set("select.ivy_mop_mode", "standard", {"options": route})
    if water is not None:
        hass.states.async_set("select.ivy_mop_intensity", "off", {"options": water})
    rb.register_roborock_adapter_for_vacuum(hass, _RVAC)
    return get_adapter_config(_RVAC)


def _pending(cfg):
    return sorted(cfg.get("_pending_live_reads") or [])


def test_vcu_1_nothing_published_names_every_unread_source(monkeypatch, hass):
    """[VCU-1] The cold-boot shape: entities may exist, none carry data yet."""
    cfg = _register(monkeypatch, hass)

    assert _pending(cfg) == sorted([
        _RVAC, "select.ivy_mop_mode", "select.ivy_mop_intensity",
    ])


def test_vcu_2_a_fully_published_device_names_nothing(monkeypatch, hass):
    """[VCU-2] THE NO-WAIT GUARD. An install whose provider was ready names nothing,
    so core arms no listener and pays nothing for a problem it does not have."""
    cfg = _register(
        monkeypatch, hass, fan=_SAROS_FAN, route=_SAROS_ROUTE, water=_SAROS_WATER
    )

    assert _pending(cfg) == []
    # And the lists really did come from the device, not the fallback.
    assert [o["value"] for o in cfg["vocabulary"]["fan_speed_options"]] == _SAROS_FAN
    assert [o["value"] for o in cfg["vocabulary"]["water_level_options"]] == [
        "off", "mild", "standard", "intense", "extreme",
    ]


def test_vcu_3_a_partial_read_names_only_what_is_still_missing(monkeypatch, hass):
    """[VCU-3] Coordinators do not all land at once, so the common case is partial.

    Naming an already-read source would re-register on every unrelated state change of
    an entity we no longer need; omitting a missing one strands that axis on the
    declared list forever.
    """
    cfg = _register(monkeypatch, hass, fan=_SAROS_FAN)

    assert _pending(cfg) == sorted(["select.ivy_mop_mode", "select.ivy_mop_intensity"])
    assert _RVAC not in _pending(cfg), "named a source that had already published"


def test_vcu_4_the_water_select_is_not_awaited_on_a_mopless_model(monkeypatch, hass):
    """[VCU-4] The S6's mop is observe-only, so the adapter declares no water axis at
    all. Waiting for a vocabulary that will never be used is a listener that never
    disarms — and it would hold the whole catch-up open for the other axes too."""
    cfg = _register(monkeypatch, hass, fan=_SAROS_FAN, route=_SAROS_ROUTE, mop=False)

    assert "select.ivy_mop_intensity" not in _pending(cfg)
    assert _pending(cfg) == []


def test_vcu_5_the_names_are_watchable_entity_ids(monkeypatch, hass):
    """[VCU-5] Core hands these straight to `async_track_state_change_event`, which
    matches on the FULL entity id. An object id ("ivy") or a bare suffix would simply
    never fire — indistinguishable from a device that never publishes, and the symptom
    would be the declared list forever with nothing in the log.
    """
    cfg = _register(monkeypatch, hass)

    for entity_id in _pending(cfg):
        assert "." in entity_id, f"{entity_id!r} is not an entity id"
        domain = entity_id.split(".", 1)[0]
        assert domain in {"vacuum", "select", "binary_sensor", "sensor"}, domain
        # Every named id is one the state machine could actually carry.
        assert entity_id.split(".", 1)[1], f"{entity_id!r} has no object id"
