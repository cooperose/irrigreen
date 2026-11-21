"""Constants for the Irrigreen integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "irrigreen"

# Config keys
CONF_HOST = "host"
CONF_NAME = "name"

DEFAULT_NAME = "Irrigreen Controller"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

# Local controller HTTP endpoints (confirmed from the app v1.15.0 + traffic).
EP_ZONES_DASHBOARD = "/system/zones_dashboard"
EP_DEVICE_STATUS = "/device_status"
EP_JOB_STATUS = "/job/status"
EP_SCHEDULES = "/system/schedules"
EP_DIRECTORY = "/directory"

# Control endpoints.
EP_JOB_START = "/job/schedule/start"
EP_JOB_EXIT = "/job/exit"
EP_SCHEDULE_PREF = "/schedule_pref"  # append /<idx>

# The endpoint used to verify we're really talking to a controller.
EP_PROBE = EP_ZONES_DASHBOARD

# Dashboard status strings that mean "actively running".
RUNNING_STATES = ("busy", "watering", "running", "on")
