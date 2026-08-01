"""Protocol driver contract and deterministic device-driver registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from .command_bundles import TclCommandBundle
from .protocol_profiles import (
    DeviceCapabilities,
    Legacy2743138Profile,
    ProtocolProfile,
    Tsl1112013595NProfile,
)


@runtime_checkable
class ProtocolDriver(Protocol):
    """Complete device-specific command and capability contract."""

    device_id: str | None
    name: str
    capabilities: DeviceCapabilities
    legacy_transport_enabled: bool
    cloud_status_family: str

    def build_mode_command(
        self, mode: str, *, target_temperature: float | None = None
    ) -> TclCommandBundle:
        """Compile a mode intent into a transport command bundle."""
        ...

    def build_temperature_command(
        self, target_temperature: float, *, current_mode: str | None = None
    ) -> TclCommandBundle:
        """Compile a target-temperature intent."""
        ...

    def build_power_off_command(self) -> TclCommandBundle:
        """Compile the device-specific power-off transaction."""
        ...

    def build_power_on_command(self) -> TclCommandBundle:
        """Compile the device-specific power-on transaction."""
        ...

    def parse_base_mode(self, base_mode: Any) -> str | None:
        """Normalize a device mode value."""
        ...


@dataclass(frozen=True)
class DriverRule:
    """One ordered driver selection rule."""

    matches: Callable[[str, str], bool]
    factory: Callable[[str | None], ProtocolDriver]


class ProtocolDriverRegistry:
    """Resolve a protocol driver from stable account/device metadata."""

    def __init__(self, rules: tuple[DriverRule, ...]) -> None:
        """Initialize the registry with ordered selection rules."""
        self._rules = rules

    def resolve(
        self,
        device_id: str | None,
        *,
        product_key: str | None = None,
    ) -> ProtocolDriver:
        """Return the first matching driver, or the compatibility driver."""
        normalized_device_id = str(device_id or "")
        normalized_product_key = str(product_key or "")
        for rule in self._rules:
            if rule.matches(normalized_device_id, normalized_product_key):
                return rule.factory(device_id)
        return ProtocolProfile(device_id=device_id)


DEFAULT_DRIVER_REGISTRY = ProtocolDriverRegistry(
    (
        DriverRule(
            matches=lambda device_id, _product_key: device_id == "2743138",
            factory=lambda _device_id: Legacy2743138Profile(device_id="2743138"),
        ),
        DriverRule(
            matches=lambda device_id, product_key: (
                product_key == "1112013595N" or device_id == "45816970"
            ),
            factory=lambda device_id: Tsl1112013595NProfile(
                device_id=device_id or "45816970"
            ),
        ),
    )
)


def resolve_protocol_driver(
    device_id: str | None,
    *,
    product_key: str | None = None,
) -> ProtocolDriver:
    """Resolve the default driver for one configured TCL device."""
    return DEFAULT_DRIVER_REGISTRY.resolve(device_id, product_key=product_key)
