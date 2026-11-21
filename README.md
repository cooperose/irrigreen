# Irrigreen for Home Assistant

A **local, cloud-free** Home Assistant integration for Irrigreen sprinkler
controllers. It talks directly to the controller on your network — no Irrigreen
account, no internet dependency.

> **v0.2 — monitoring + control.** Reads everything the controller exposes
> locally, and now controls it: run zones/valves, enable/disable schedules, and
> stop. All local, no cloud.

## What you get

**Monitoring**
- **Per zone:** watering on/off, status, and water-adjustment %
- **Valves:** running state
- **Master valves:** active state and live current draw (mA)
- **Flow sensors:** active state and pulse count (disabled by default; enable per sensor)
- **Schedules:** each slot's state (watering / enabled / disabled) with start time, duration, type and cycle
- **System:** automatic-watering state and system-wide water adjustment %
- **Job feed:** current/last run with start and stop reason

**Control**
- **Zone switch** per head — turn on to quick-run it, off to stop
- **Valve switch** per valve — quick-run / stop
- **Schedule switch** per slot — enable / disable
- **Zone enable** switch per head — enable / disable the head (config)
- **Double coverage** switch per head (config)
- **Stop all watering** button
- **Calibrate** button per head
- **Test devices** button (diagnostic scan — detects stuck valves / faults)
- **Scan for devices** button (identify devices on the bus)
- **Services** for automations: `irrigreen.run_zone`, `irrigreen.run_valve`,
  `irrigreen.stop`, `irrigreen.set_schedule`

**Health, water & config**
- **Problem** binary sensor + **Active errors** sensor — per-head and per-valve
  faults (stuck valves etc.), with details in attributes
- **Last run water use** (gallons) with 7-day / 13-week history
- **Firmware version**, **Cloud connection** (state + RSSI), **Weather adjustment**
- **Per-head type** (XR for v2 / HydroBoost for v3) with config attributes:
  double coverage, flow restrictor, XP, plant/soil/sun, calibration, sqft, head id

Run commands are issued exactly as the official app issues them (verified against
the app's own traffic), using each device's descriptor from the controller's
`/directory`. Note: a quick-run uses the controller's default duration; turning a
switch off stops the current job.

## Requirements

- Home Assistant 2024.1 or newer
- Home Assistant must be able to reach the controller's IP address. On a
  segmented (VLAN) network the controller is usually isolated, so make sure
  there's a firewall rule allowing HA to reach the controller on TCP 80, and use
  the controller's IP directly (mDNS discovery does not cross VLANs).

## Install (HACS)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/cooperose/irrigreen`, category **Integration**.
2. Install **Irrigreen**, then restart Home Assistant.
3. Settings → Devices & Services → **Add Integration** → **Irrigreen**.
4. Enter the controller's IP address (e.g. `192.168.1.50`).

## Install (manual)

Copy `custom_components/irrigreen` into your HA `config/custom_components/`
folder and restart.

## How it works

The controller serves a small local HTTP API. This integration polls these
read-only endpoints every 30 seconds:

| Endpoint | Provides |
|---|---|
| `/system/zones_dashboard` | zones, valves, water adjustments, live status |
| `/device_status` | master valves (current), flow sensors, workers |
| `/system/schedules` | schedule slots |
| `/job/status` | current/last job |

## Privacy / security

This integration stores only the controller's IP address. It sends nothing to
any cloud. The diagnostics download redacts any address/serial/Wi-Fi fields as a
safety net.

## Roadmap

- Writable flow restrictor and plant/soil/sun (same `/sprinkler_pref` endpoint; needs each save captured)
- Blowout / winterize action
- Head renaming from HA

Note: controller software-update availability is cloud-managed and not exposed by
the local API, so the integration reports the current firmware version but does
not trigger updates.

## Disclaimer

Not affiliated with or endorsed by Irrigreen. Built by reverse-engineering the
local API for personal use. Use at your own risk.
