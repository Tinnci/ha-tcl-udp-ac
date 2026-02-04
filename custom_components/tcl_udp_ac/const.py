"""Constants for tcl_udp_ac."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "tcl_udp_ac"

# UDP ports
UDP_BROADCAST_PORT = 10074
UDP_COMMAND_PORT = 10075

# Default values
DEFAULT_NAME = "TCL AC"
