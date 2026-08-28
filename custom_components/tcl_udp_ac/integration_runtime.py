"""Domain-wide shared runtime resources."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .const import DOMAIN
from .credential_manager import CredentialManager
from .udp_hub import UdpHub

_RUNTIME_KEY = "runtime"


@dataclass
class IntegrationRuntime:
    """Resources shared by every configured TCL device."""

    udp_hub: UdpHub = field(default_factory=UdpHub)
    credential_manager: CredentialManager | None = None


def get_integration_runtime(hass: Any) -> IntegrationRuntime:
    """Return the single integration runtime attached to Home Assistant."""
    if not hasattr(hass, "data"):
        hass.data = {}
    domain_data = hass.data.setdefault(DOMAIN, {})
    runtime = domain_data.get(_RUNTIME_KEY)
    if runtime is None:
        runtime = IntegrationRuntime()
        domain_data[_RUNTIME_KEY] = runtime
    return runtime
