"""Config + options flow for SimplyPrint."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    SimplyPrintApiClient,
    SimplyPrintAuthError,
    SimplyPrintError,
)
from .const import (
    CONF_CAMERA_URLS,
    CONF_COMPANY_ID,
    CONF_PRINTER_IDS,
    CONF_USE_WEBHOOKS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SimplyPrintConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the SimplyPrint config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_key: str | None = None
        self._company_id: str | None = None
        self._printers: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key: str = user_input[CONF_API_KEY].strip()
            company_id: str = str(user_input[CONF_COMPANY_ID]).strip()

            await self.async_set_unique_id(f"{company_id}")
            self._abort_if_unique_id_configured()

            client = SimplyPrintApiClient(
                async_get_clientsession(self.hass), api_key, company_id
            )
            try:
                await client.test_credentials()
                printers = await client.list_printers()
            except SimplyPrintAuthError:
                errors["base"] = "invalid_auth"
            except SimplyPrintError as err:
                _LOGGER.warning("SimplyPrint connection error: %s", err)
                errors["base"] = "cannot_connect"
            else:
                if not printers:
                    errors["base"] = "no_printers"
                else:
                    self._api_key = api_key
                    self._company_id = company_id
                    self._printers = printers
                    return await self.async_step_select_printers()

        schema = vol.Schema(
            {
                vol.Required(CONF_COMPANY_ID): str,
                vol.Required(CONF_API_KEY): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "panel_url": "https://simplyprint.io/panel/account/api"
            },
        )

    async def async_step_select_printers(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            picked: list[int] = [int(p) for p in user_input[CONF_PRINTER_IDS]]
            return self.async_create_entry(
                title=f"SimplyPrint ({self._company_id})",
                data={
                    CONF_COMPANY_ID: self._company_id,
                    CONF_API_KEY: self._api_key,
                    CONF_PRINTER_IDS: picked,
                },
                options={
                    CONF_USE_WEBHOOKS: user_input.get(CONF_USE_WEBHOOKS, False),
                    CONF_CAMERA_URLS: {},
                },
            )

        printer_choices = {str(p["id"]): _printer_label(p) for p in self._printers}
        all_ids = list(printer_choices)
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_PRINTER_IDS, default=all_ids
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=k, label=v)
                            for k, v in printer_choices.items()
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(CONF_USE_WEBHOOKS, default=False): bool,
            }
        )
        return self.async_show_form(
            step_id="select_printers",
            data_schema=schema,
            description_placeholders={
                "count": str(len(printer_choices)),
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            api_key: str = user_input[CONF_API_KEY].strip()
            company_id: str = entry.data[CONF_COMPANY_ID]

            client = SimplyPrintApiClient(
                async_get_clientsession(self.hass), api_key, company_id
            )
            try:
                await client.test_credentials()
            except SimplyPrintAuthError:
                errors["base"] = "invalid_auth"
            except SimplyPrintError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: api_key}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return SimplyPrintOptionsFlow()


def _printer_label(row: dict[str, Any]) -> str:
    """Build a friendly label for the printer-pick step."""
    inner = row.get("printer") or {}
    name = inner.get("name") or f"Printer {row.get('id')}"
    model = (inner.get("model") or {}).get("name")
    if model:
        return f"{name} — {model}"
    return name


class SimplyPrintOptionsFlow(OptionsFlow):
    """Manage per-printer camera URLs and webhook toggle."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self.config_entry
        printer_ids: list[int] = entry.data.get(CONF_PRINTER_IDS, [])
        existing_cameras: dict[str, str] = entry.options.get(CONF_CAMERA_URLS) or {}

        if user_input is not None:
            cameras: dict[str, str] = {}
            for pid in printer_ids:
                key = f"camera_{pid}"
                value = (user_input.get(key) or "").strip()
                if value:
                    cameras[str(pid)] = value
            return self.async_create_entry(
                title="",
                data={
                    CONF_USE_WEBHOOKS: user_input.get(
                        CONF_USE_WEBHOOKS,
                        entry.options.get(CONF_USE_WEBHOOKS, False),
                    ),
                    CONF_CAMERA_URLS: cameras,
                },
            )

        schema_dict: dict[Any, Any] = {
            vol.Optional(
                CONF_USE_WEBHOOKS,
                default=entry.options.get(CONF_USE_WEBHOOKS, False),
            ): bool,
        }
        for pid in printer_ids:
            schema_dict[
                vol.Optional(
                    f"camera_{pid}",
                    description={"suggested_value": existing_cameras.get(str(pid), "")},
                )
            ] = str

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )
