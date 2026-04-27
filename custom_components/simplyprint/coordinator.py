"""DataUpdateCoordinator for SimplyPrint."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    SimplyPrintApiClient,
    SimplyPrintAuthError,
    SimplyPrintError,
    SimplyPrintRateLimitError,
)
from .const import (
    ACTIVE_PRINT_STATES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FAST_SCAN_INTERVAL,
    RATE_LIMIT_BACKOFF,
)

_LOGGER = logging.getLogger(__name__)


class SimplyPrintCoordinator(DataUpdateCoordinator[dict[int, dict[str, Any]]]):
    """Polls SimplyPrint and exposes a {printer_id: printer_row} dict.

    Speeds up polling automatically while any tracked printer is actively
    printing, slows back down to default when everything goes idle.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: SimplyPrintApiClient,
        printer_ids: list[int],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({entry.title})",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.entry = entry
        self.client = client
        self.printer_ids = printer_ids

    async def _async_update_data(self) -> dict[int, dict[str, Any]]:
        try:
            rows = await self.client.get_printers_bulk(self.printer_ids)
        except SimplyPrintAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SimplyPrintRateLimitError as err:
            # Back off for a minute on 429
            self.update_interval = RATE_LIMIT_BACKOFF
            raise UpdateFailed("Rate limited by SimplyPrint") from err
        except SimplyPrintError as err:
            raise UpdateFailed(str(err)) from err

        result = {int(row["id"]): row for row in rows if "id" in row}

        # Adapt poll cadence based on activity
        any_active = any(
            (row.get("printer") or {}).get("state") in ACTIVE_PRINT_STATES
            for row in result.values()
        )
        new_interval: timedelta = (
            FAST_SCAN_INTERVAL if any_active else DEFAULT_SCAN_INTERVAL
        )
        if self.update_interval != new_interval:
            self.update_interval = new_interval

        return result

    def push_printer_row(self, row: dict[str, Any]) -> None:
        """Inject a fresh row from a webhook delivery without polling."""
        if "id" not in row:
            return
        merged = dict(self.data or {})
        merged[int(row["id"])] = row
        self.async_set_updated_data(merged)
