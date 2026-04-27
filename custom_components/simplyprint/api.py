"""Async aiohttp client for the SimplyPrint REST API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from aiohttp import ClientResponseError, ClientSession

from .const import (
    API_ACTION_CANCEL,
    API_ACTION_CLEAR_BED,
    API_ACTION_CREATE_JOB,
    API_ACTION_PAUSE,
    API_ACTION_RESUME,
    API_ACTION_SEND_GCODE,
    API_BASE,
    API_PRINTERS_GET,
    API_TEST_PATH,
    API_WEBHOOKS_CREATE,
    API_WEBHOOKS_DELETE,
    API_WEBHOOKS_GET,
)

_LOGGER = logging.getLogger(__name__)


class SimplyPrintError(Exception):
    """Base error from the SimplyPrint client."""


class SimplyPrintAuthError(SimplyPrintError):
    """Raised when the API key is missing, wrong, or lacks permission."""


class SimplyPrintRateLimitError(SimplyPrintError):
    """Raised when SimplyPrint returns HTTP 429."""


class SimplyPrintNotEntitledError(SimplyPrintError):
    """Raised when an endpoint requires a higher SimplyPrint plan."""


class SimplyPrintApiClient:
    """Thin async wrapper around the SimplyPrint HTTP API.

    All endpoints are scoped under /{company_id}/, authenticate with
    X-API-KEY, and return a {status, message, ...} envelope.
    """

    def __init__(
        self,
        session: ClientSession,
        api_key: str,
        company_id: int | str,
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._company_id = str(company_id)

    @property
    def company_id(self) -> str:
        return self._company_id

    def _url(self, path: str) -> str:
        return f"{API_BASE}/{self._company_id}/{path.lstrip('/')}"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "X-API-KEY": self._api_key,
        }
        if json is not None:
            headers["Content-Type"] = "application/json"

        try:
            async with self._session.request(
                method,
                self._url(path),
                params=params,
                json=json,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status == 401:
                    raise SimplyPrintAuthError("API key rejected (401)")
                if resp.status == 403:
                    text = await resp.text()
                    # 403 can mean either missing perm or plan-gated endpoint.
                    if "plan" in text.lower() or "not enabled" in text.lower():
                        raise SimplyPrintNotEntitledError(text)
                    raise SimplyPrintAuthError(f"Forbidden (403): {text}")
                if resp.status == 429:
                    raise SimplyPrintRateLimitError("Rate limited (429)")
                if resp.status >= 500:
                    raise SimplyPrintError(f"Server error {resp.status}")
                resp.raise_for_status()
                payload = await resp.json(content_type=None)
        except ClientResponseError as err:
            raise SimplyPrintError(f"HTTP {err.status}: {err.message}") from err
        except asyncio.TimeoutError as err:
            raise SimplyPrintError("Request timed out") from err
        except aiohttp.ClientError as err:
            raise SimplyPrintError(f"Connection error: {err}") from err

        if not isinstance(payload, dict):
            raise SimplyPrintError(f"Unexpected response: {payload!r}")

        if payload.get("status") is False:
            message = payload.get("message") or "Unknown SimplyPrint error"
            # 200 with status:false. Catch the auth-flavored ones.
            if "API key" in str(message) or "logged in" in str(message):
                raise SimplyPrintAuthError(message)
            if "access" in str(message).lower():
                raise SimplyPrintAuthError(message)
            raise SimplyPrintError(message)

        return payload

    # ------------------------------------------------------------------ auth

    async def test_credentials(self) -> bool:
        """Return True if the API key + company id pair is valid.

        Raises SimplyPrintAuthError on bad creds, SimplyPrintError otherwise.
        """
        await self._request("GET", API_TEST_PATH)
        return True

    # -------------------------------------------------------------- printers

    async def list_printers(
        self,
        *,
        page: int = 1,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Return all printers across pages."""
        printers: list[dict[str, Any]] = []
        while True:
            payload = await self._request(
                "POST",
                API_PRINTERS_GET,
                json={"page": page, "page_size": page_size},
            )
            data = payload.get("data") or []
            if isinstance(data, dict):
                printers.append(data)
                break
            printers.extend(data)
            page_amount = int(payload.get("page_amount") or 1)
            if page >= page_amount:
                break
            page += 1
        return printers

    async def get_printer(self, printer_id: int) -> dict[str, Any] | None:
        """Return a single printer row (or None if not visible)."""
        payload = await self._request(
            "GET",
            API_PRINTERS_GET,
            params={"pid": str(printer_id)},
        )
        data = payload.get("data")
        if isinstance(data, list):
            return data[0] if data else None
        return data

    async def get_printers_bulk(self, printer_ids: list[int]) -> list[dict[str, Any]]:
        """Fetch a known set of printers in one call (comma-separated pids)."""
        if not printer_ids:
            return []
        pid_param = ",".join(str(p) for p in printer_ids)
        payload = await self._request(
            "GET",
            API_PRINTERS_GET,
            params={"pid": pid_param},
        )
        data = payload.get("data") or []
        if isinstance(data, dict):
            return [data]
        return data

    # ---------------------------------------------------------------- actions

    async def pause(self, printer_id: int) -> None:
        await self._request("POST", API_ACTION_PAUSE, params={"pid": str(printer_id)})

    async def resume(self, printer_id: int) -> None:
        await self._request("POST", API_ACTION_RESUME, params={"pid": str(printer_id)})

    async def cancel(
        self,
        printer_id: int,
        *,
        comment: str | None = None,
        return_to_queue: bool = False,
    ) -> None:
        body: dict[str, Any] = {}
        if comment is not None:
            body["comment"] = comment
        if return_to_queue:
            body["return_to_queue"] = True
        await self._request(
            "POST",
            API_ACTION_CANCEL,
            params={"pid": str(printer_id)},
            json=body or None,
        )

    async def clear_bed(self, printer_id: int) -> None:
        await self._request(
            "POST", API_ACTION_CLEAR_BED, params={"pid": str(printer_id)}
        )

    async def send_gcode(self, printer_id: int, gcode: str) -> None:
        await self._request(
            "POST",
            API_ACTION_SEND_GCODE,
            params={"pid": str(printer_id)},
            json={"gcode": gcode},
        )

    async def start_queued_job(
        self, printer_id: int, queue_file_id: int
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            API_ACTION_CREATE_JOB,
            params={"pid": str(printer_id)},
            json={"queue_file": queue_file_id},
        )

    async def start_next_queue_item(self, printer_id: int) -> dict[str, Any]:
        return await self._request(
            "POST",
            API_ACTION_CREATE_JOB,
            params={"pid": str(printer_id)},
            json={"next_queue_item": True},
        )

    # ---------------------------------------------------------------- webhooks

    async def list_webhooks(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", API_WEBHOOKS_GET)
        return payload.get("data") or []

    async def create_webhook(
        self,
        *,
        name: str,
        url: str,
        secret: str,
        events: list[str],
        description: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": name,
            "url": url,
            "secret": secret,
            "enabled": True,
            "events": events,
        }
        if description:
            body["description"] = description
        payload = await self._request("POST", API_WEBHOOKS_CREATE, json=body)
        return payload.get("webhook") or {}

    async def delete_webhook(self, webhook_id: int) -> None:
        await self._request("POST", API_WEBHOOKS_DELETE, json={"id": int(webhook_id)})
