"""Constants for tcl_udp_ac."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "tcl_udp_ac"

# UDP ports
UDP_BROADCAST_PORT = 10074
UDP_COMMAND_PORT = 10075

# Default values
DEFAULT_NAME = "TCL AC"
DEFAULT_ACTION_JID = "homeassistant@tcl.com/ha-plugin-001"
DEFAULT_ACTION_SOURCE = "1"
DEFAULT_ACCOUNT = "homeassistant"

# Config keys
CONF_ACTION_JID = "action_jid"
CONF_ACTION_SOURCE = "action_source"
CONF_ACCOUNT = "account"

# Protocol value mappings
# HVAC Modes (BaseMode tag values)
MODE_COOL = "cool"
MODE_HEAT = "heat"
MODE_FAN = "fan"
MODE_DEHUMI = "dehumi"
MODE_AUTO = "selffeel"

# Fan Speeds (WindSpeed tag values)
FAN_HIGH = "high"
FAN_MIDDLE = "middle"
FAN_LOW = "low"
FAN_AUTO = "auto"

# Swing/Boolean values
VALUE_ON = "on"
VALUE_OFF = "off"
