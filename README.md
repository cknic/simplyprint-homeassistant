# SimplyPrint — Home Assistant integration

A custom integration that connects [SimplyPrint](https://simplyprint.io) (cloud 3D-printer management) to Home Assistant.

[![hassfest](https://github.com/cknic/simplyprint-homeassistant/actions/workflows/hassfest.yml/badge.svg)](https://github.com/cknic/simplyprint-homeassistant/actions/workflows/hassfest.yml)
[![HACS](https://github.com/cknic/simplyprint-homeassistant/actions/workflows/validate.yml/badge.svg)](https://github.com/cknic/simplyprint-homeassistant/actions/workflows/validate.yml)

## Features

Per printer:

- Sensors: state, progress, time remaining, ETA, current file, current layer, filament used, hotend & bed actual/target temps
- Binary sensors: online, printing, error, awaiting bed clear, has camera
- Buttons: pause, resume, cancel, clear bed
- Camera entity (optional, you supply the MJPEG/snapshot URL — SimplyPrint's public API does not expose one)
- Services for raw control: `pause`, `resume`, `cancel`, `clear_bed`, `send_gcode`, `start_queued_job`, `start_next_queue_item`
- Webhook receiver for real-time `job.*` events (Print Farm plan only)

## Install

### HACS (recommended)

1. HACS → Integrations → ⋮ → *Custom repositories*
2. Add `https://github.com/cknic/simplyprint-homeassistant` as type **Integration**
3. Install **SimplyPrint** and restart Home Assistant
4. Settings → Devices & services → **Add Integration** → SimplyPrint

### Manual

Copy `custom_components/simplyprint/` into `<config>/custom_components/` and restart Home Assistant.

## Configure

You'll need:

- Your numeric **Company ID** (SimplyPrint panel URL: `https://simplyprint.io/panel/<company_id>/...`)
- An **API key** created at *Account → API*

Then choose which printers to track from the list. After setup, the **Configure** button on the integration card lets you:

- Paste a webcam stream URL per printer (e.g. `http://octopi.local/webcam/?action=stream`)
- Toggle real-time webhooks (requires SimplyPrint Print Farm plan; falls back to polling otherwise)

## Polling cadence

- Default: 30 s
- While any tracked printer is actively printing: 10 s
- On HTTP 429 (rate-limited): 60 s back-off

## Webhook events

When webhooks are enabled, every SimplyPrint delivery is also fired on the HA event bus as `simplyprint_webhook` so you can build automations:

```yaml
automation:
  - alias: Notify when print finishes
    trigger:
      platform: event
      event_type: simplyprint_webhook
      event_data:
        event: job.done
    action:
      service: notify.mobile_app
      data:
        title: "Print finished"
        message: "{{ trigger.event.data.data.job.file }}"
```

Subscribed events: `job.started`, `job.paused`, `job.resumed`, `job.cancelled`, `job.done`, `job.failed`, `job.bed_cleared`.

## Services example

```yaml
service: simplyprint.cancel
data:
  printer_id: 1234
  comment: "Failed first layer"
  return_to_queue: true
```

## Limitations

- SimplyPrint's REST API does not expose webcam URLs — supply your own per printer.
- Webhook registration requires the Print Farm plan. The integration auto-detects this and falls back to polling.
- Some endpoints (`start_next_queue_item`, farm overview) require Print Farm; pause/resume/cancel work on every paid plan.

## License

MIT
