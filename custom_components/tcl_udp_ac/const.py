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
