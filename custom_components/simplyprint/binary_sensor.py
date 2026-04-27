"""Binary sensor platform for SimplyPrint."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ACTIVE_PRINT_STATES,
    CONF_PRINTER_IDS,
    DOMAIN,
    STATE_ERROR,
)
from .entity import SimplyPrintEntity


@dataclass(frozen=True, kw_only=True)
class SimplyPrintBinaryDescription(BinarySensorEntityDescription):
    is_on_fn: Callable[[dict[str, Any]], bool | None]


def _is_online(row: dict[str, Any]) -> bool | None:
    printer = row.get("printer") or {}
    return printer.get("online")


def _is_printing(row: dict[str, Any]) -> bool:
    printer = row.get("printer") or {}
    return printer.get("state") in ACTIVE_PRINT_STATES


def _has_error(row: dict[str, Any]) -> bool:
    printer = row.get("printer") or {}
    return printer.get("state") == STATE_ERROR


def _bed_clear_needed(row: dict[str, Any]) -> bool:
    return bool((row.get("printer") or {}).get("awaitingBedClear"))


def _has_camera(row: dict[str, Any]) -> bool:
    return bool((row.get("printer") or {}).get("hasCam"))


BINARY_SENSORS: tuple[SimplyPrintBinaryDescription, ...] = (
    SimplyPrintBinaryDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=_is_online,
    ),
    SimplyPrintBinaryDescription(
        key="printing",
        translation_key="printing",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_is_printing,
    ),
    SimplyPrintBinaryDescription(
        key="error",
        translation_key="error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=_has_error,
    ),
    SimplyPrintBinaryDescription(
        key="awaiting_bed_clear",
        translation_key="awaiting_bed_clear",
        is_on_fn=_bed_clear_needed,
    ),
    SimplyPrintBinaryDescription(
        key="has_camera",
        translation_key="has_camera",
        entity_registry_enabled_default=False,
        is_on_fn=_has_camera,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    printer_ids: list[int] = entry.data.get(CONF_PRINTER_IDS, [])
    entities: list[SimplyPrintBinarySensor] = []
    for pid in printer_ids:
        for desc in BINARY_SENSORS:
            entities.append(SimplyPrintBinarySensor(runtime.coordinator, pid, desc))
    async_add_entities(entities)


class SimplyPrintBinarySensor(SimplyPrintEntity, BinarySensorEntity):
    """Binary sensor backed by a row-based predicate."""

    entity_description: SimplyPrintBinaryDescription

    def __init__(
        self,
        coordinator,
        printer_id: int,
        description: SimplyPrintBinaryDescription,
    ) -> None:
        super().__init__(coordinator, printer_id)
        self.entity_description = description
        self._attr_unique_id = f"{printer_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.is_on_fn(self._row)
