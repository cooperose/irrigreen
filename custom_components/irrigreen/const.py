"""Constants for the Irrigreen integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "irrigreen"

# Config keys
CONF_HOST = "host"
CONF_NAME = "name"

DEFAULT_NAME = "Irrigreen Controller"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

# Local controller HTTP endpoints (read-only; discovered from the app v1.15.0).
EP_ZONES_DASHBOARD = "/system/zones_dashboard"
EP_DEVICE_STATUS = "/device_status"
EP_JOB_STATUS = "/job/status"
EP_SCHEDULES = "/system/schedules"

# The endpoint used to verify we're really talking to a controller.
EP_PROBE = EP_ZONES_DASHBOARD
