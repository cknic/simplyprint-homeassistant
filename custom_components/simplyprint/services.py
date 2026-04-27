"""Service registration for SimplyPrint."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv

from .api import SimplyPrintApiClient, SimplyPrintError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_PAUSE = "pause"
SERVICE_RESUME = "resume"
SERVICE_CANCEL = "cancel"
SERVICE_CLEAR_BED = "clear_bed"
SERVICE_SEND_GCODE = "send_gcode"
SERVICE_START_QUEUED = "start_queued_job"
SERVICE_START_NEXT = "start_next_queue_item"

ATTR_PRINTER_ID = "printer_id"
ATTR_COMMENT = "comment"
ATTR_RETURN_TO_QUEUE = "return_to_queue"
ATTR_GCODE = "gcode"
ATTR_QUEUE_FILE = "queue_file"

_PRINTER_SCHEMA = vol.Schema({vol.Required(ATTR_PRINTER_ID): vol.Coerce(int)})

_CANCEL_SCHEMA = _PRINTER_SCHEMA.extend(
    {
        vol.Optional(ATTR_COMMENT): cv.string,
        vol.Optional(ATTR_RETURN_TO_QUEUE, default=False): cv.boolean,
    }
)

_GCODE_SCHEMA = _PRINTER_SCHEMA.extend({vol.Required(ATTR_GCODE): cv.string})

_QUEUE_SCHEMA = _PRINTER_SCHEMA.extend({vol.Required(ATTR_QUEUE_FILE): vol.Coerce(int)})


def _resolve_client(hass: HomeAssistant, printer_id: int) -> SimplyPrintApiClient:
    """Find the API client whose config entry tracks this printer id."""
    domain_data: dict[str, Any] = hass.data.get(DOMAIN, {})
    for runtime in domain_data.values():
        if printer_id in runtime.coordinator.printer_ids:
            return runtime.client
    raise ServiceValidationError(
        f"Printer {printer_id} is not tracked by any SimplyPrint config entry"
    )


async def _wrap(call_label: str, awaitable):
    try:
        return await awaitable
    except SimplyPrintError as err:
        raise HomeAssistantError(f"{call_label} failed: {err}") from err


def async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_PAUSE):
        return

    async def _pause(call: ServiceCall) -> None:
        pid = int(call.data[ATTR_PRINTER_ID])
        await _wrap("pause", _resolve_client(hass, pid).pause(pid))

    async def _resume(call: ServiceCall) -> None:
        pid = int(call.data[ATTR_PRINTER_ID])
        await _wrap("resume", _resolve_client(hass, pid).resume(pid))

    async def _cancel(call: ServiceCall) -> None:
        pid = int(call.data[ATTR_PRINTER_ID])
        await _wrap(
            "cancel",
            _resolve_client(hass, pid).cancel(
                pid,
                comment=call.data.get(ATTR_COMMENT),
                return_to_queue=call.data.get(ATTR_RETURN_TO_QUEUE, False),
            ),
        )

    async def _clear_bed(call: ServiceCall) -> None:
        pid = int(call.data[ATTR_PRINTER_ID])
        await _wrap("clear_bed", _resolve_client(hass, pid).clear_bed(pid))

    async def _send_gcode(call: ServiceCall) -> None:
        pid = int(call.data[ATTR_PRINTER_ID])
        gcode = call.data[ATTR_GCODE]
        await _wrap("send_gcode", _resolve_client(hass, pid).send_gcode(pid, gcode))

    async def _start_queued(call: ServiceCall) -> None:
        pid = int(call.data[ATTR_PRINTER_ID])
        queue_file = int(call.data[ATTR_QUEUE_FILE])
        await _wrap(
            "start_queued_job",
            _resolve_client(hass, pid).start_queued_job(pid, queue_file),
        )

    async def _start_next(call: ServiceCall) -> None:
        pid = int(call.data[ATTR_PRINTER_ID])
        await _wrap(
            "start_next_queue_item",
            _resolve_client(hass, pid).start_next_queue_item(pid),
        )

    hass.services.async_register(DOMAIN, SERVICE_PAUSE, _pause, schema=_PRINTER_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_RESUME, _resume, schema=_PRINTER_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_CANCEL, _cancel, schema=_CANCEL_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_BED, _clear_bed, schema=_PRINTER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SEND_GCODE, _send_gcode, schema=_GCODE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_START_QUEUED, _start_queued, schema=_QUEUE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_START_NEXT, _start_next, schema=_PRINTER_SCHEMA
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    for svc in (
        SERVICE_PAUSE,
        SERVICE_RESUME,
        SERVICE_CANCEL,
        SERVICE_CLEAR_BED,
        SERVICE_SEND_GCODE,
        SERVICE_START_QUEUED,
        SERVICE_START_NEXT,
    ):
        if hass.services.has_service(DOMAIN, svc):
            hass.services.async_remove(DOMAIN, svc)
