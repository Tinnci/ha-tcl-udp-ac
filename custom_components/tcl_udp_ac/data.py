"""Custom types for tcl_udp_ac."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import TclUdpApiClient
    from .coordinator import TclUdpDataUpdateCoordinator
    from .token_manager import TokenManager


type TclUdpConfigEntry = ConfigEntry[TclUdpData]


@dataclass
class TclUdpData:
    """Data for the TCL UDP AC integration."""

    client: TclUdpApiClient
    coordinator: TclUdpDataUpdateCoordinator
    integration: Integration
    token_manager: TokenManager | None = None
