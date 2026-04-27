"""Button platform for SimplyPrint (pause / resume / cancel / clear bed)."""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import SimplyPrintApiClient, SimplyPrintError
from .const import (
    ACTIVE_PRINT_STATES,
    CONF_PRINTER_IDS,
    DOMAIN,
    STATE_PAUSED,
)
from .entity import SimplyPrintEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SimplyPrintButtonDescription(ButtonEntityDescription):
    press_fn: Callable[[SimplyPrintApiClient, int], Awaitable[None]]
    available_when_state_in: tuple[str, ...] | None = None


BUTTONS: tuple[SimplyPrintButtonDescription, ...] = (
    SimplyPrintButtonDescription(
        key="pause",
        translation_key="pause",
        press_fn=lambda client, pid: client.pause(pid),
        available_when_state_in=tuple(ACTIVE_PRINT_STATES),
    ),
    SimplyPrintButtonDescription(
        key="resume",
        translation_key="resume",
        press_fn=lambda client, pid: client.resume(pid),
        available_when_state_in=(STATE_PAUSED,),
    ),
    SimplyPrintButtonDescription(
        key="cancel",
        translation_key="cancel",
        press_fn=lambda client, pid: client.cancel(pid),
        available_when_state_in=tuple(ACTIVE_PRINT_STATES) + (STATE_PAUSED,),
    ),
    SimplyPrintButtonDescription(
        key="clear_bed",
        translation_key="clear_bed",
        press_fn=lambda client, pid: client.clear_bed(pid),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    printer_ids: list[int] = entry.data.get(CONF_PRINTER_IDS, [])
    entities: list[SimplyPrintButton] = []
    for pid in printer_ids:
        for desc in BUTTONS:
            entities.append(
                SimplyPrintButton(runtime.coordinator, runtime.client, pid, desc)
            )
    async_add_entities(entities)


class SimplyPrintButton(SimplyPrintEntity, ButtonEntity):
    """A printer-control button."""

    entity_description: SimplyPrintButtonDescription

    def __init__(
        self,
        coordinator,
        client: SimplyPrintApiClient,
        printer_id: int,
        description: SimplyPrintButtonDescription,
    ) -> None:
        super().__init__(coordinator, printer_id)
        self._client = client
        self.entity_description = description
        self._attr_unique_id = f"{printer_id}_btn_{description.key}"

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        gate = self.entity_description.available_when_state_in
        if gate is None:
            return True
        return self._printer.get("state") in gate

    async def async_press(self) -> None:
        try:
            await self.entity_description.press_fn(self._client, self._printer_id)
        except SimplyPrintError as err:
            raise HomeAssistantError(
                f"SimplyPrint {self.entity_description.key} failed: {err}"
            ) from err
        await self.coordinator.async_request_refresh()
