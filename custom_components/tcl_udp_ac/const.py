"""Constants for tcl_udp_ac."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "tcl_udp_ac"

# UDP ports
UDP_BROADCAST_PORT = 10074
UDP_COMMAND_PORT = 10075

# Default values
DEFAULT_NAME = "TCL AC"
DEFAULT_ACTION_JID = "14422778@tcl.com/PH-android-zx02-1"
DEFAULT_ACTION_SOURCE = "1"
DEFAULT_ACCOUNT = "14422778"
DEFAULT_CLOUD_ENABLED = True
DEFAULT_CLOUD_TID = ""
DEFAULT_CLOUD_TOKEN = ""
DEFAULT_CLOUD_FROM = ""
DEFAULT_CLOUD_TO = ""
DEFAULT_CLOUD_BASE_URL = "https://io.zx.tcljd.com"
DEFAULT_CLOUD_CONTROL = True
DEFAULT_CLOUD_USER_AGENT = "com.tcl.tclplus/6.0.3, Android"
DEFAULT_CLOUD_PLATFORM = "android"
DEFAULT_CLOUD_APP_PACKAGE = "com.tcl.tclplus"
DEFAULT_CLOUD_SYSTEM_VERSION = "16"
DEFAULT_CLOUD_BRAND = "X1032K11J"
DEFAULT_CLOUD_APP_VERSION = "4.0.9"
DEFAULT_CLOUD_SDK_VERSION = "6.0.3"
DEFAULT_CLOUD_CHANNEL = "xiaomi"
DEFAULT_CLOUD_APP_BUILD_VERSION = "4.0.9.0"
DEFAULT_CLOUD_T_APP_VERSION = "4.0.9.0"
DEFAULT_CLOUD_T_PLATFORM_TYPE = "Android"
DEFAULT_CLOUD_T_STORE_UUID = "TCL+"
DEFAULT_CLOUD_ORIGIN = "https://h5.zx.tcljd.com"
DEFAULT_CLOUD_X_REQUESTED_WITH = "com.tcl.tclplus"
DEFAULT_CLOUD_ACCEPT = "text/plain, */*; q=0.01"
DEFAULT_CLOUD_ACCEPT_ENCODING = "gzip, deflate, br, zstd"
DEFAULT_CLOUD_ACCEPT_LANGUAGE = "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7"

# Config keys
CONF_ACTION_JID = "action_jid"
CONF_ACTION_SOURCE = "action_source"
CONF_ACCOUNT = "account"
CONF_CLOUD_ENABLED = "cloud_enabled"
CONF_CLOUD_TID = "cloud_tid"
CONF_CLOUD_TOKEN = "cloud_access_token"  # noqa: S105
CONF_CLOUD_FROM = "cloud_from"
CONF_CLOUD_TO = "cloud_to"
CONF_CLOUD_BASE_URL = "cloud_base_url"
CONF_CLOUD_CONTROL = "cloud_control"
CONF_CLOUD_USER_AGENT = "cloud_user_agent"
CONF_CLOUD_PLATFORM = "cloud_platform"
CONF_CLOUD_APP_PACKAGE = "cloud_app_package"
CONF_CLOUD_SYSTEM_VERSION = "cloud_system_version"
CONF_CLOUD_BRAND = "cloud_brand"
CONF_CLOUD_APP_VERSION = "cloud_app_version"
CONF_CLOUD_SDK_VERSION = "cloud_sdk_version"
CONF_CLOUD_CHANNEL = "cloud_channel"
CONF_CLOUD_APP_BUILD_VERSION = "cloud_app_build_version"
CONF_CLOUD_T_APP_VERSION = "cloud_t_app_version"
CONF_CLOUD_T_PLATFORM_TYPE = "cloud_t_platform_type"
CONF_CLOUD_T_STORE_UUID = "cloud_t_store_uuid"
CONF_CLOUD_ORIGIN = "cloud_origin"
CONF_CLOUD_X_REQUESTED_WITH = "cloud_x_requested_with"
CONF_CLOUD_ACCEPT = "cloud_accept"
CONF_CLOUD_ACCEPT_ENCODING = "cloud_accept_encoding"
CONF_CLOUD_ACCEPT_LANGUAGE = "cloud_accept_language"

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
