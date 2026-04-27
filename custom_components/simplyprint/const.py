"""Constants for the SimplyPrint integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "simplyprint"
MANUFACTURER: Final = "SimplyPrint"

# Config entry keys
CONF_API_KEY: Final = "api_key"
CONF_COMPANY_ID: Final = "company_id"
CONF_PRINTER_IDS: Final = "printer_ids"
CONF_USE_WEBHOOKS: Final = "use_webhooks"
CONF_WEBHOOK_ID: Final = "webhook_id"
CONF_WEBHOOK_SECRET: Final = "webhook_secret"
CONF_CAMERA_URLS: Final = "camera_urls"  # dict of {printer_id: url}

# Defaults / tunables
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=30)
FAST_SCAN_INTERVAL: Final = timedelta(seconds=10)  # while a print is active
RATE_LIMIT_BACKOFF: Final = timedelta(seconds=60)

# API
API_BASE: Final = "https://api.simplyprint.io"
API_TEST_PATH: Final = "account/Test"
API_PRINTERS_GET: Final = "printers/Get"
API_ACTION_PAUSE: Final = "printers/actions/Pause"
API_ACTION_RESUME: Final = "printers/actions/Resume"
API_ACTION_CANCEL: Final = "printers/actions/Cancel"
API_ACTION_CREATE_JOB: Final = "printers/actions/CreateJob"
API_ACTION_CLEAR_BED: Final = "printers/actions/ClearBed"
API_ACTION_SEND_GCODE: Final = "printers/actions/SendGcode"
API_WEBHOOKS_CREATE: Final = "webhooks/Create"
API_WEBHOOKS_DELETE: Final = "webhooks/Delete"
API_WEBHOOKS_GET: Final = "webhooks/Get"

# Printer states (from SimplyPrint)
STATE_OPERATIONAL: Final = "operational"
STATE_PRINTING: Final = "printing"
STATE_PAUSED: Final = "paused"
STATE_PAUSING: Final = "pausing"
STATE_RESUMING: Final = "resuming"
STATE_CANCELLING: Final = "cancelling"
STATE_ERROR: Final = "error"
STATE_DOWNLOADING: Final = "downloading"
STATE_IN_MAINTENANCE: Final = "in_maintenance"
STATE_PRINT_PENDING: Final = "print_pending"
STATE_UNKNOWN: Final = "unknown"
STATE_OFFLINE: Final = "offline"

ACTIVE_PRINT_STATES: Final = frozenset(
    {STATE_PRINTING, STATE_PAUSING, STATE_RESUMING, STATE_CANCELLING, STATE_DOWNLOADING}
)

# Webhook events SimplyPrint can send
WEBHOOK_EVENT_JOB_STARTED: Final = "job.started"
WEBHOOK_EVENT_JOB_PAUSED: Final = "job.paused"
WEBHOOK_EVENT_JOB_RESUMED: Final = "job.resumed"
WEBHOOK_EVENT_JOB_CANCELLED: Final = "job.cancelled"
WEBHOOK_EVENT_JOB_DONE: Final = "job.done"
WEBHOOK_EVENT_JOB_FAILED: Final = "job.failed"
WEBHOOK_EVENT_JOB_BED_CLEARED: Final = "job.bed_cleared"
WEBHOOK_EVENT_TEST: Final = "test"

DEFAULT_WEBHOOK_EVENTS: Final = [
    WEBHOOK_EVENT_JOB_STARTED,
    WEBHOOK_EVENT_JOB_PAUSED,
    WEBHOOK_EVENT_JOB_RESUMED,
    WEBHOOK_EVENT_JOB_CANCELLED,
    WEBHOOK_EVENT_JOB_DONE,
    WEBHOOK_EVENT_JOB_FAILED,
    WEBHOOK_EVENT_JOB_BED_CLEARED,
]

# HA event fired for SimplyPrint webhook deliveries
HA_EVENT_WEBHOOK: Final = "simplyprint_webhook"

# Platforms
PLATFORMS: Final = ["sensor", "binary_sensor", "button", "camera"]
