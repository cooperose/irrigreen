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
EP_SYSTEM_INFO = "/system/info"
EP_CONNECTION = "/system/connection"
EP_DASHBOARD = "/system/dashboard"
EP_IGSPRINKLER = "/igsprinkler"  # /<zone>/summary
EP_VALVE = "/valve"  # /<n>/summary
EP_SPRINKLER_PREF = "/sprinkler_pref"  # /<zone>
EP_SYSTEM_PREF = "/system_pref"
EP_SYSTEM_SETUP = "/system/setup"  # /<setup_num>
SETUPS = (1, 2)  # controller setup banks (8 zones each)

# Head hardware type (desc "t") -> friendly name.
HEAD_TYPE_NAMES = {"s2ble": "XR", "s3": "HydroBoost", "v": "Valve"}

# Control endpoints.
EP_JOB_START = "/job/schedule/start"
EP_JOB_EXIT = "/job/exit"
EP_JOB_CALIBRATE = "/job/calibrate/start"
EP_JOB_DIAGNOSTIC = "/job/diagnostic/start"
EP_JOB_SCAN = "/job/scan_identify/start"
EP_SCHEDULE_PREF = "/schedule_pref"  # append /<idx>

# The endpoint used to verify we're really talking to a controller.
EP_PROBE = EP_ZONES_DASHBOARD

# Dashboard status strings that mean "actively running".
RUNNING_STATES = ("busy", "watering", "running", "on")
