# SimplyPrint for Home Assistant

A Home Assistant integration for [SimplyPrint](https://simplyprint.io), the cloud 3D-printer management platform. Polls the SimplyPrint REST API for printer state, exposes services to pause/resume/cancel prints, and (optionally) registers a SimplyPrint webhook for real-time job events.

## What you get per printer

- **Sensors**: state, progress %, time remaining, ETA, current file, current layer, filament used, hotend & bed actual + target temps
- **Binary sensors**: online, printing, error, awaiting bed clear, has camera
- **Buttons**: pause, resume, cancel, clear bed
- **Camera**: optional, when you supply an MJPEG/snapshot URL in options
- **Services**: `simplyprint.pause`, `simplyprint.resume`, `simplyprint.cancel`, `simplyprint.clear_bed`, `simplyprint.send_gcode`, `simplyprint.start_queued_job`, `simplyprint.start_next_queue_item`

## Setup

1. Sign in to SimplyPrint and grab your numeric **Company ID** and an **API key** (Account → API).
2. In Home Assistant: *Settings → Devices & services → Add Integration → SimplyPrint*.
3. Pick which printers to track.
4. (Optional) In the integration's **Configure** menu: paste an MJPEG URL per printer to enable a camera entity, and toggle webhooks if you have the Print Farm plan.

## Notes

- Webhooks require the Print Farm plan. Without it, the integration polls every 30s (10s while a print is active).
- SimplyPrint's API does not expose webcam URLs, only a `hasCam` flag. For camera entities, point the integration at your printer host's MJPEG stream (OctoPrint, Mainsail, Fluidd, Bambu, …).
