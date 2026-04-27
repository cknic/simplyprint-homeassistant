"""Camera platform for SimplyPrint.

SimplyPrint's public API does not expose a webcam URL, only a `hasCam` flag.
Users supply a stream/snapshot URL per printer in the integration's options
flow; we expose a camera entity for each printer that has one configured.
"""
from __future__ import annotations

import logging

from homeassistant.components.camera import (
    Camera,
    CameraEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    CONF_CAMERA_URLS,
    CONF_PRINTER_IDS,
    DOMAIN,
)
from .entity import SimplyPrintEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    printer_ids: list[int] = entry.data.get(CONF_PRINTER_IDS, [])
    cameras: dict[str, str] = entry.options.get(CONF_CAMERA_URLS) or {}

    entities: list[Camera] = []
    for pid in printer_ids:
        url = cameras.get(str(pid))
        if not url:
            continue
        entities.append(SimplyPrintCamera(runtime.coordinator, pid, url))

    async_add_entities(entities)


class SimplyPrintCamera(SimplyPrintEntity, Camera):
    """User-supplied MJPEG/snapshot URL exposed as a camera entity."""

    _attr_translation_key = "camera"
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, coordinator, printer_id: int, url: str) -> None:
        SimplyPrintEntity.__init__(self, coordinator, printer_id)
        Camera.__init__(self)
        self._url = url
        self._attr_unique_id = f"{printer_id}_camera"

    async def stream_source(self) -> str | None:
        return self._url

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        # Best-effort still grab from the configured URL. Many SimplyPrint
        # users will plug in an MJPEG stream URL whose first frame works as a
        # snapshot; some will provide a dedicated /snapshot URL.
        try:
            client = get_async_client(self.hass, verify_ssl=False)
            response = await client.get(self._url, timeout=10.0)
            if response.status_code == 200:
                ctype = response.headers.get("content-type", "")
                if ctype.startswith("image/"):
                    return response.content
                # Fall through if MJPEG — the stream API will handle it.
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.debug("Snapshot fetch failed for %s: %s", self._url, err)
        return None
