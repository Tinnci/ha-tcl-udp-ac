"""Account-scoped discovery of device descriptors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .account_client import TclAccountAuthError
from .config_settings import entry_value
from .const import CONF_CLOUD_TOKEN
from .credential_manager import CloudAuthRejectedError
from .device_descriptor import DeviceDescriptor

if TYPE_CHECKING:
    from .account_client import AccountClient
    from .token_manager import TokenManager


@dataclass(frozen=True)
class AccountDeviceInventory:
    """A current account view separated from per-device config entries."""

    account_id: str
    devices: tuple[DeviceDescriptor, ...]
    configured_device_ids: frozenset[str]

    @property
    def available_devices(self) -> tuple[DeviceDescriptor, ...]:
        """Return devices that do not already have a config entry."""
        return tuple(
            device
            for device in self.devices
            if device.device_id not in self.configured_device_ids
        )

    def find(self, device_id: str) -> DeviceDescriptor | None:
        """Find one descriptor by its stable cloud device ID."""
        return next(
            (device for device in self.devices if device.device_id == device_id),
            None,
        )


class AccountDeviceCatalog:
    """Adapter that loads inventory through the existing token lifecycle seam."""

    def __init__(
        self,
        account_client: AccountClient,
        token_manager: TokenManager,
        source_entry: Any,
    ) -> None:
        self._account_client = account_client
        self._token_manager = token_manager
        self._source_entry = source_entry

    async def async_load(
        self,
        *,
        account_id: str,
        configured_device_ids: frozenset[str],
    ) -> AccountDeviceInventory:
        """Fetch account devices, refreshing once only after explicit rejection."""

        async def operation() -> list[DeviceDescriptor]:
            token = str(entry_value(self._source_entry, CONF_CLOUD_TOKEN, "") or "")
            try:
                return await self._account_client.async_list_devices(token)
            except TclAccountAuthError as exc:
                raise CloudAuthRejectedError from exc

        devices = await self._token_manager.async_authenticated_request(operation)
        return AccountDeviceInventory(
            account_id=account_id,
            devices=tuple(devices),
            configured_device_ids=configured_device_ids,
        )
