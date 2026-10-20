"""Card-facing snapshot services + pause-timeout settings.

Five services, all supports_response=True:
- get_dashboard_snapshot: unified card snapshot
- get_upkeep_snapshot: maintenance/dock-event aggregate
- get_maintenance_source_candidates: entities that could back the maintenance counter
- get_pause_timeout_settings: read persisted default
- set_pause_timeout_settings: write persisted default
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from ..const import (
    DOMAIN,
    SERVICE_GET_DASHBOARD_SNAPSHOT,
    SERVICE_GET_PAUSE_TIMEOUT_SETTINGS,
    SERVICE_GET_MAINTENANCE_SOURCE_CANDIDATES,
    SERVICE_GET_UPKEEP_SNAPSHOT,
    SERVICE_SET_PAUSE_TIMEOUT_SETTINGS,
    SERVICE_SET_VACUUM_CAPABILITY,
)
from ._common import (
    VACUUM_MAP_SCHEMA,
    VACUUM_ONLY_SCHEMA,
    get_manager,
    is_managed_vacuum,
    require_managed_vacuum,
    resolved_call_data,
    unmanaged_vacuum_read_result,
)

_LOGGER = logging.getLogger(__name__)


SERVICES = (
    SERVICE_GET_DASHBOARD_SNAPSHOT,
    SERVICE_GET_UPKEEP_SNAPSHOT,
    SERVICE_GET_MAINTENANCE_SOURCE_CANDIDATES,
    SERVICE_GET_PAUSE_TIMEOUT_SETTINGS,
    SERVICE_SET_PAUSE_TIMEOUT_SETTINGS,
    SERVICE_SET_VACUUM_CAPABILITY,
)


_PAUSE_TIMEOUT_SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("pause_timeout_minutes_default"): vol.All(
            vol.Coerce(int), vol.Range(min=0)
        ),
    }
)


_SET_VACUUM_CAPABILITY_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("capability"): cv.string,
        # Optional, and absent means CLEAR — hand the question back to detection.
        # A user who answers wrongly must not be stuck with it.
        vol.Optional("supported"): vol.Any(cv.boolean, None),
    }
)


async def _handle_set_vacuum_capability(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Record the user's answer about what their vacuum can do.

    Some capabilities we DERIVE and some we GUESS, and the two have been stored as the
    same value — a model-family guess reading as False denies a feature to hardware
    that has it. This lets the person who can actually see the machine settle it.
    """
    data = resolved_call_data(hass, call)
    vacuum_entity_id = data["vacuum_entity_id"]
    require_managed_vacuum(hass, vacuum_entity_id)
    manager = get_manager(hass)
    result = manager.set_vacuum_capability(
        vacuum_entity_id=vacuum_entity_id,
        capability=data["capability"],
        supported=data.get("supported"),
    )
    await manager.async_save()
    return result


async def _handle_get_dashboard_snapshot(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return unified dashboard snapshot for one vacuum/map."""
    # INKV8ZQD: a read answers empty-with-a-reason.
    if not is_managed_vacuum(hass, call.data["vacuum_entity_id"]):
        return unmanaged_vacuum_read_result(call.data["vacuum_entity_id"])
    manager = get_manager(hass)
    resolved = resolved_call_data(hass, call)
    # Pre-warm the map_state_source cache ASYNC (off-loop .storage read for the Eufy
    # backend; in-memory introspect for Roborock) so the sync snapshot below can
    # include the VA-owned read of the provider's segmentation without doing the
    # blocking read itself. Degrades to an absent marker on any failure.
    await manager.async_refresh_map_state_source(**resolved)
    # Must NOT use async_add_executor_job here — get_dashboard_snapshot calls
    # hass.bus.async_fire internally (via _maybe_roll_current_room_by_timing),
    # which requires the event loop thread.
    payload = manager.get_dashboard_snapshot(**resolved)
    _LOGGER.debug("get_dashboard_snapshot complete: %s", payload)
    return payload


async def _handle_get_upkeep_snapshot(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return upkeep snapshot for one vacuum."""
    # INKV8ZQD: a read answers empty-with-a-reason.
    if not is_managed_vacuum(hass, call.data["vacuum_entity_id"]):
        return unmanaged_vacuum_read_result(call.data["vacuum_entity_id"])
    payload = get_manager(hass).get_upkeep_snapshot(**call.data)
    _LOGGER.debug("get_upkeep_snapshot complete: %s", payload)
    return payload


async def _handle_get_maintenance_source_candidates(
    hass: HomeAssistant, call: ServiceCall
) -> dict:
    """Return the entities that could back this vacuum's maintenance counter.

    READ-ONLY, and deliberately NOT a field on the upkeep snapshot. The underlying sweep walks
    the entity registry and reads a state per sibling -- 300 entities on one live machine -- for
    a list that is wanted twice in a vacuum's life. Computing it when the picker opens also means
    the user sees what is true NOW; candidates appear and disappear as integrations reload.

    Wrapped in a dict rather than returned bare because a HA service response must be a mapping.
    """
    # INKV8ZQD: a read answers empty-with-a-reason.
    if not is_managed_vacuum(hass, call.data["vacuum_entity_id"]):
        return unmanaged_vacuum_read_result(call.data["vacuum_entity_id"])
    candidates = get_manager(hass).get_maintenance_source_candidates(**call.data)
    _LOGGER.debug(
        "get_maintenance_source_candidates: %d candidate(s) for %s",
        len(candidates), call.data["vacuum_entity_id"],
    )
    return {"candidates": candidates}


async def _handle_get_pause_timeout_settings(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return persisted default pause-timeout settings for one vacuum."""
    # INKV8ZQD: a read answers empty-with-a-reason. Defence in depth here --
    # the manager method this calls is the one that used to MINT the vacuum
    # bucket (fixed 2026-08-18); this stops the call reaching it at all.
    if not is_managed_vacuum(hass, call.data["vacuum_entity_id"]):
        return unmanaged_vacuum_read_result(call.data["vacuum_entity_id"])
    payload = get_manager(hass).get_pause_timeout_settings(**call.data)
    _LOGGER.debug("get_pause_timeout_settings complete: %s", payload)
    return payload


async def _handle_set_pause_timeout_settings(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Persist default pause-timeout settings for one vacuum."""
    # INKV8ZQD: a write to an unmanaged vacuum refuses.
    require_managed_vacuum(hass, call.data["vacuum_entity_id"])
    payload = get_manager(hass).set_pause_timeout_settings(**call.data)
    _LOGGER.debug("set_pause_timeout_settings complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


def register(hass: HomeAssistant) -> None:
    """Register snapshot services."""

    async def get_dashboard_snapshot(call: ServiceCall) -> dict:
        return await _handle_get_dashboard_snapshot(hass, call)

    async def get_upkeep_snapshot(call: ServiceCall) -> dict:
        return await _handle_get_upkeep_snapshot(hass, call)

    async def get_maintenance_source_candidates(call: ServiceCall) -> dict:
        return await _handle_get_maintenance_source_candidates(hass, call)

    async def get_pause_timeout_settings(call: ServiceCall) -> dict:
        return await _handle_get_pause_timeout_settings(hass, call)

    async def set_pause_timeout_settings(call: ServiceCall) -> dict:
        return await _handle_set_pause_timeout_settings(hass, call)

    async def set_vacuum_capability(call: ServiceCall) -> dict:
        return await _handle_set_vacuum_capability(hass, call)

    hass.services.async_register(
        DOMAIN, SERVICE_GET_DASHBOARD_SNAPSHOT, get_dashboard_snapshot,
        schema=VACUUM_MAP_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_UPKEEP_SNAPSHOT, get_upkeep_snapshot,
        schema=VACUUM_ONLY_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_MAINTENANCE_SOURCE_CANDIDATES, get_maintenance_source_candidates,
        schema=VACUUM_ONLY_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_PAUSE_TIMEOUT_SETTINGS, get_pause_timeout_settings,
        schema=VACUUM_ONLY_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_PAUSE_TIMEOUT_SETTINGS, set_pause_timeout_settings,
        schema=_PAUSE_TIMEOUT_SETTINGS_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_VACUUM_CAPABILITY, set_vacuum_capability,
        schema=_SET_VACUUM_CAPABILITY_SCHEMA, supports_response=True,
    )
