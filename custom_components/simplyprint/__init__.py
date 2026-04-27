"""SimplyPrint integration for Home Assistant."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SimplyPrintApiClient, SimplyPrintAuthError, SimplyPrintError
from .const import (
    CONF_COMPANY_ID,
    CONF_PRINTER_IDS,
    CONF_USE_WEBHOOKS,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import SimplyPrintCoordinator
from .services import async_register_services, async_unregister_services
from .webhook import async_setup_webhook, async_teardown_webhook

_LOGGER = logging.getLogger(__name__)


@dataclass
class SimplyPrintRuntimeData:
    """Per-config-entry runtime state."""

    client: SimplyPrintApiClient
    coordinator: SimplyPrintCoordinator
    webhook_id: str | None = None
    webhook_unregister: Callable[[], Any] | None = None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SimplyPrint from a config entry."""
    session = async_get_clientsession(hass)
    client = SimplyPrintApiClient(
        session,
        api_key=entry.data[CONF_API_KEY],
        company_id=entry.data[CONF_COMPANY_ID],
    )

    try:
        await client.test_credentials()
    except SimplyPrintAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except SimplyPrintError as err:
        raise ConfigEntryNotReady(str(err)) from err

    printer_ids: list[int] = list(entry.data.get(CONF_PRINTER_IDS, []))
    coordinator = SimplyPrintCoordinator(hass, entry, client, printer_ids)
    await coordinator.async_config_entry_first_refresh()

    runtime = SimplyPrintRuntimeData(client=client, coordinator=coordinator)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async_register_services(hass)

    if entry.options.get(CONF_USE_WEBHOOKS):
        try:
            await async_setup_webhook(hass, entry, runtime)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.warning(
                "Could not register SimplyPrint webhook (%s). "
                "Falling back to polling.",
                err,
            )

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a SimplyPrint config entry."""
    runtime: SimplyPrintRuntimeData | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )
    if runtime is not None:
        await async_teardown_webhook(hass, entry, runtime)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if not hass.data.get(DOMAIN):
            async_unregister_services(hass)

    return unload_ok
