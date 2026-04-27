"""Shared entity base class for SimplyPrint."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import SimplyPrintCoordinator


class SimplyPrintEntity(CoordinatorEntity[SimplyPrintCoordinator]):
    """Base class binding entities to a specific printer id."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SimplyPrintCoordinator, printer_id: int
    ) -> None:
        super().__init__(coordinator)
        self._printer_id = printer_id

    @property
    def _row(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get(self._printer_id, {}) or {}

    @property
    def _printer(self) -> dict[str, Any]:
        return self._row.get("printer") or {}

    @property
    def _job(self) -> dict[str, Any] | None:
        job = self._row.get("job")
        return job if isinstance(job, dict) else None

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return bool(self._row)

    @property
    def device_info(self) -> DeviceInfo:
        printer = self._printer
        model = (printer.get("model") or {}).get("name")
        brand = (printer.get("model") or {}).get("brand")
        sw = printer.get("spVersion") or printer.get("firmwareVersion")
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._printer_id))},
            name=printer.get("name") or f"SimplyPrint {self._printer_id}",
            manufacturer=brand or MANUFACTURER,
            model=model,
            sw_version=sw,
            configuration_url=(
                f"https://simplyprint.io/panel/printers/{self._printer_id}"
            ),
        )
