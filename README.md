# Irrigreen for Home Assistant

A **local, cloud-free** Home Assistant integration for Irrigreen sprinkler
controllers. It talks directly to the controller on your network — no Irrigreen
account, no internet dependency.

> **v0.1 — monitoring.** This first release reads and reports everything the
> controller exposes locally. Control (run zone, run schedule, stop, rain delay,
> blowout, calibrate) is the next release.

## What you get

- **Per zone:** watering on/off, status, and water-adjustment %
- **Valves:** running state
- **Master valves:** active state and live current draw (mA)
- **Flow sensors:** active state and pulse count (disabled by default; enable per sensor)
- **Schedules:** each slot's state (watering / enabled / disabled) with start time, duration, type and cycle
- **System:** automatic-watering state and system-wide water adjustment %
- **Job feed:** current/last run with start and stop reason

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

- v0.2: control actions (run zone, run schedule, stop, rain delay, blowout, calibrate)
- v0.3: schedule editing; flow-based water-usage sensors

## Disclaimer

Not affiliated with or endorsed by Irrigreen. Built by reverse-engineering the
local API for personal use. Use at your own risk.
