"""Sensor platform for SimplyPrint."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_PRINTER_IDS,
    DOMAIN,
    STATE_OFFLINE,
)
from .entity import SimplyPrintEntity


@dataclass(frozen=True, kw_only=True)
class SimplyPrintSensorDescription(SensorEntityDescription):
    """Sensor description with a value extractor."""

    value_fn: Callable[[dict[str, Any]], Any]


def _state_value(row: dict[str, Any]) -> str | None:
    printer = row.get("printer") or {}
    if printer.get("online") is False:
        return STATE_OFFLINE
    return printer.get("state")


def _hotend_actual(row: dict[str, Any]) -> float | None:
    tools = ((row.get("printer") or {}).get("temps") or {}).get("current", {}).get(
        "tool"
    )
    if isinstance(tools, list) and tools:
        return _to_float(tools[0])
    return None


def _hotend_target(row: dict[str, Any]) -> float | None:
    tools = ((row.get("printer") or {}).get("temps") or {}).get("target", {}).get(
        "tool"
    )
    if isinstance(tools, list) and tools:
        return _to_float(tools[0])
    return None


def _bed_actual(row: dict[str, Any]) -> float | None:
    return _to_float(
        ((row.get("printer") or {}).get("temps") or {}).get("current", {}).get("bed")
    )


def _bed_target(row: dict[str, Any]) -> float | None:
    return _to_float(
        ((row.get("printer") or {}).get("temps") or {}).get("target", {}).get("bed")
    )


def _progress(row: dict[str, Any]) -> float | None:
    job = row.get("job")
    if isinstance(job, dict):
        return _to_float(job.get("percentage"))
    return None


def _time_left(row: dict[str, Any]) -> int | None:
    job = row.get("job")
    if isinstance(job, dict):
        v = job.get("time_left")
        if isinstance(v, (int, float)):
            return int(v)
    return None


def _eta(row: dict[str, Any]) -> datetime | None:
    secs = _time_left(row)
    if secs is None:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=secs)


def _current_file(row: dict[str, Any]) -> str | None:
    job = row.get("job")
    if isinstance(job, dict):
        return job.get("file")
    return None


def _current_layer(row: dict[str, Any]) -> int | None:
    job = row.get("job")
    if isinstance(job, dict):
        v = job.get("current_layer")
        if isinstance(v, int):
            return v
    return None


def _filament_used_mm(row: dict[str, Any]) -> float | None:
    job = row.get("job")
    if not isinstance(job, dict):
        return None
    analysis = job.get("analysis") or {}
    fil = analysis.get("filament")
    if isinstance(fil, list) and fil:
        try:
            return float(sum(x for x in fil if isinstance(x, (int, float))))
        except (TypeError, ValueError):
            return None
    return None


def _to_float(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


SENSORS: tuple[SimplyPrintSensorDescription, ...] = (
    SimplyPrintSensorDescription(
        key="state",
        translation_key="state",
        value_fn=_state_value,
    ),
    SimplyPrintSensorDescription(
        key="progress",
        translation_key="progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_progress,
    ),
    SimplyPrintSensorDescription(
        key="time_remaining",
        translation_key="time_remaining",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        value_fn=_time_left,
    ),
    SimplyPrintSensorDescription(
        key="eta",
        translation_key="eta",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_eta,
    ),
    SimplyPrintSensorDescription(
        key="current_file",
        translation_key="current_file",
        value_fn=_current_file,
    ),
    SimplyPrintSensorDescription(
        key="current_layer",
        translation_key="current_layer",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_current_layer,
    ),
    SimplyPrintSensorDescription(
        key="filament_used",
        translation_key="filament_used",
        native_unit_of_measurement="mm",
        state_class=SensorStateClass.TOTAL,
        value_fn=_filament_used_mm,
    ),
    SimplyPrintSensorDescription(
        key="hotend_temp",
        translation_key="hotend_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_hotend_actual,
    ),
    SimplyPrintSensorDescription(
        key="hotend_target",
        translation_key="hotend_target",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_hotend_target,
    ),
    SimplyPrintSensorDescription(
        key="bed_temp",
        translation_key="bed_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_bed_actual,
    ),
    SimplyPrintSensorDescription(
        key="bed_target",
        translation_key="bed_target",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_bed_target,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    printer_ids: list[int] = entry.data.get(CONF_PRINTER_IDS, [])
    entities: list[SimplyPrintSensor] = []
    for pid in printer_ids:
        for desc in SENSORS:
            entities.append(SimplyPrintSensor(runtime.coordinator, pid, desc))
    async_add_entities(entities)


class SimplyPrintSensor(SimplyPrintEntity, SensorEntity):
    """Sensor entity backed by a value-fn against the printer row."""

    entity_description: SimplyPrintSensorDescription

    def __init__(
        self,
        coordinator,
        printer_id: int,
        description: SimplyPrintSensorDescription,
    ) -> None:
        super().__init__(coordinator, printer_id)
        self.entity_description = description
        self._attr_unique_id = f"{printer_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self._row)
