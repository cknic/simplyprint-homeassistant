"""Webhook plumbing for SimplyPrint.

SimplyPrint sends real-time job/printer events to a URL we register with them.
Each delivery includes the secret we set, echoed in the X-SP-Secret header.
We register the webhook with HA's `webhook` component so it's exposed at
/api/webhook/<webhook_id>, then verify the secret and dispatch.

Note: webhook registration on SimplyPrint requires the Print Farm plan.
If registration fails, callers should fall back to polling.
"""

from __future__ import annotations

import hmac
import logging
import secrets
from typing import TYPE_CHECKING, Any

from aiohttp.web import Request, Response

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import (
    CONF_WEBHOOK_ID,
    CONF_WEBHOOK_SECRET,
    DEFAULT_WEBHOOK_EVENTS,
    DOMAIN,
    HA_EVENT_WEBHOOK,
)

if TYPE_CHECKING:
    from . import SimplyPrintRuntimeData

_LOGGER = logging.getLogger(__name__)


async def async_setup_webhook(
    hass: HomeAssistant,
    entry: ConfigEntry,
    runtime: "SimplyPrintRuntimeData",
) -> None:
    """Register a webhook with HA and with SimplyPrint."""
    webhook_id: str = entry.data.get(CONF_WEBHOOK_ID) or secrets.token_hex(16)
    secret: str = entry.data.get(CONF_WEBHOOK_SECRET) or secrets.token_hex(32)

    # Persist the generated ids so they survive reloads
    if (
        entry.data.get(CONF_WEBHOOK_ID) != webhook_id
        or entry.data.get(CONF_WEBHOOK_SECRET) != secret
    ):
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_WEBHOOK_ID: webhook_id,
                CONF_WEBHOOK_SECRET: secret,
            },
        )

    handler = _make_handler(runtime, secret)

    webhook.async_register(
        hass,
        DOMAIN,
        f"SimplyPrint ({entry.title})",
        webhook_id,
        handler,
        allowed_methods=["POST"],
    )

    # Build a fully-qualified URL SimplyPrint can actually reach.
    try:
        base_url = get_url(
            hass,
            allow_internal=False,
            allow_cloud=True,
            prefer_external=True,
            require_ssl=False,
        )
    except NoURLAvailableError as err:
        webhook.async_unregister(hass, webhook_id)
        raise RuntimeError(
            "No external URL configured for Home Assistant; cannot register "
            "SimplyPrint webhook. Set External URL under Settings -> System -> "
            "Network or use Nabu Casa, then re-enable webhooks."
        ) from err

    public_url = f"{base_url.rstrip('/')}/api/webhook/{webhook_id}"
    if not public_url.startswith(("http://", "https://")):
        webhook.async_unregister(hass, webhook_id)
        raise RuntimeError(f"Refusing to register non-HTTP webhook URL: {public_url}")

    try:
        webhook_info = await runtime.client.create_webhook(
            name=f"Home Assistant ({entry.title})",
            url=public_url,
            secret=secret,
            events=DEFAULT_WEBHOOK_EVENTS,
            description="Auto-registered by Home Assistant SimplyPrint integration.",
        )
    except Exception:
        webhook.async_unregister(hass, webhook_id)
        raise

    runtime.webhook_id = webhook_id

    sp_webhook_id = webhook_info.get("id")
    if sp_webhook_id is not None:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, "sp_webhook_id": int(sp_webhook_id)},
        )

    _LOGGER.info(
        "Registered SimplyPrint webhook -> %s (sp id=%s)",
        public_url,
        sp_webhook_id,
    )


async def async_teardown_webhook(
    hass: HomeAssistant,
    entry: ConfigEntry,
    runtime: "SimplyPrintRuntimeData",
) -> None:
    """Unregister the HA webhook view and (best effort) the SimplyPrint side."""
    if runtime.webhook_id:
        webhook.async_unregister(hass, runtime.webhook_id)
        runtime.webhook_id = None

    sp_webhook_id = entry.data.get("sp_webhook_id")
    if sp_webhook_id is not None:
        try:
            await runtime.client.delete_webhook(int(sp_webhook_id))
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.debug("Could not delete SimplyPrint webhook: %s", err)


def _make_handler(runtime: "SimplyPrintRuntimeData", expected_secret: str):
    """Build a closure that validates and dispatches a webhook delivery."""

    async def _handle(
        hass: HomeAssistant, webhook_id: str, request: Request
    ) -> Response:
        provided = request.headers.get("X-SP-Secret")
        if provided is None or not hmac.compare_digest(provided, expected_secret):
            _LOGGER.warning("Rejected SimplyPrint webhook with bad/missing X-SP-Secret")
            return Response(status=401)

        try:
            payload: dict[str, Any] = await request.json()
        except ValueError:
            return Response(status=400)

        event = payload.get("event")
        data = payload.get("data") or {}

        # Surface the event in HA's event bus so users can build automations
        hass.bus.async_fire(
            HA_EVENT_WEBHOOK,
            {
                "event": event,
                "timestamp": payload.get("timestamp"),
                "data": data,
            },
        )

        # If the payload includes a printer id we track, request a refresh so
        # progress/temps update immediately (webhook events don't carry temps).
        printer_block = data.get("printer") or (data.get("job") or {}).get("printer")
        if isinstance(printer_block, dict):
            pid = printer_block.get("id")
            if isinstance(pid, int) and pid in runtime.coordinator.printer_ids:
                await runtime.coordinator.async_request_refresh()

        return Response(status=200)

    return _handle
