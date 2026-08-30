"""Per-device runtime facade for state, commands, and transports."""

from __future__ import annotations

import time
from inspect import isawaitable
from typing import Any

from .command_bundles import CommandReceipt
from .command_tracker import CommandTracker
from .device_state import Observation, StateReducer, StateSource


class DeviceSession:
    """Expose one device to Home Assistant through a stable runtime boundary."""

    def __init__(self, client: Any) -> None:
        """Initialize a session around one compatibility transport client."""
        self._client = client
        self._state = StateReducer()
        self._commands = CommandTracker()
        self._status_callback: Any = None

    @property
    def transport_client(self) -> Any:
        """Return the compatibility transport client during migration."""
        return self._client

    @property
    def cloud_enabled(self) -> bool:
        """Return whether cloud status fallback is available."""
        return bool(self._client.cloud_enabled)

    @property
    def cloud_statistics_enabled(self) -> bool:
        """Return whether cloud report statistics are available."""
        return bool(self._client.cloud_statistics_enabled)

    async def async_start_listener(self, status_callback: Any) -> None:
        """Start transport listeners and normalize local push updates."""
        self._status_callback = status_callback
        await self._client.async_start_listener(self._async_handle_udp_status)

    async def _async_handle_udp_status(self, status: dict[str, Any]) -> None:
        snapshot = self.observe(StateSource.UDP, status)
        if self._status_callback is not None:
            result = self._status_callback(snapshot)
            if isawaitable(result):
                await result

    def observe(
        self,
        source: StateSource,
        values: dict[str, Any],
        *,
        received_at: float | None = None,
    ) -> dict[str, Any]:
        """Apply one normalized observation and return the device snapshot."""
        snapshot = self._state.apply(
            Observation(
                source=source,
                received_at=time.monotonic() if received_at is None else received_at,
                values=dict(values),
            )
        )
        return snapshot.as_dict()

    def merge_derived(self, values: dict[str, Any]) -> dict[str, Any]:
        """Merge integration-derived fields such as report statistics."""
        unsupported = set(values) - {"energy_statistics"}
        if unsupported:
            msg = f"Unsupported derived state fields: {', '.join(sorted(unsupported))}"
            raise ValueError(msg)
        return self.observe(StateSource.DERIVED, values)

    async def async_request_status(self) -> None:
        """Request a fresh local status."""
        await self._client.async_request_status()

    async def async_fetch_cloud_status(
        self,
        retries: int = 1,
        retry_delay: float = 1.0,
    ) -> dict[str, Any] | None:
        """Fetch and reconcile cloud fallback status."""
        status = await self._client.async_fetch_cloud_status(
            retries=retries,
            retry_delay=retry_delay,
        )
        if status:
            return self.observe(StateSource.CLOUD, status)
        return None

    async def async_fetch_cloud_energy_statistics(self) -> dict[str, Any] | None:
        """Fetch current cloud report statistics."""
        return await self._client.async_fetch_cloud_energy_statistics()

    def get_last_status(self) -> dict[str, Any]:
        """Return the reconciled state, seeding compatibility clients when needed."""
        state = self._state.as_dict()
        if state:
            return state
        legacy_state = self._client.get_last_status()
        if legacy_state:
            return self.observe(StateSource.DERIVED, legacy_state)
        return {}

    def pending_command_confirmation(
        self, command_id: str | None = None
    ) -> dict[str, Any] | None:
        """Return a specific or latest pending command expectation."""
        pending = self._commands.pending(command_id)
        return pending.as_dict() if pending is not None else None

    def clear_pending_command_confirmation(self, command_id: str | None = None) -> None:
        """Complete a specific or latest pending command."""
        pending = self._commands.pending(command_id)
        if pending is not None:
            self._commands.complete(pending.command_id)

    def annotate_pending_command(
        self,
        command_id: str | None,
        *,
        entity_id: str | None,
        context_id: str | None,
    ) -> None:
        """Associate a tracked command with its HA entity dispatch context."""
        if command_id is not None:
            self._commands.annotate(
                command_id,
                entity_id=entity_id,
                context_id=context_id,
            )

    def _track_command(self, receipt: CommandReceipt) -> str | None:
        if not receipt.delivery.accepted:
            return None
        return self._commands.record(receipt)

    async def _run_command(
        self, method_name: str, *args: Any, **kwargs: Any
    ) -> str | None:
        receipt = await getattr(self._client, method_name)(*args, **kwargs)
        if not isinstance(receipt, CommandReceipt):
            return None
        return self._track_command(receipt)

    async def async_set_power(self, *, power: bool) -> str | None:
        """Set device power and return its confirmation identifier."""
        return await self._run_command("async_set_power", power=power)

    async def async_set_power_mode(
        self, *, power: bool, mode_str: str | None = None
    ) -> str | None:
        """Set power and mode as one compatibility transaction."""
        return await self._run_command(
            "async_set_power_mode", power=power, mode_str=mode_str
        )

    async def async_set_mode_profile(
        self,
        mode_str: str,
        *,
        target_temperature: float | None = None,
    ) -> str | None:
        """Set HVAC mode through the selected driver."""
        return await self._run_command(
            "async_set_mode_profile",
            mode_str,
            target_temperature=target_temperature,
        )

    async def async_set_temperature(self, temperature: float) -> str | None:
        """Set target temperature."""
        return await self._run_command("async_set_temperature", temperature)

    async def async_set_fan_speed(self, speed_str: str) -> str | None:
        """Set fan speed."""
        return await self._run_command("async_set_fan_speed", speed_str)

    async def async_set_swing(self, *, vertical: bool, horizontal: bool) -> str | None:
        """Set vertical and horizontal swing state."""
        return await self._run_command(
            "async_set_swing", vertical=vertical, horizontal=horizontal
        )

    async def async_set_eco_mode(self, *, enabled: bool) -> str | None:
        """Enable or disable ECO mode."""
        return await self._run_command("async_set_eco_mode", enabled=enabled)

    async def async_set_display(self, *, enabled: bool) -> str | None:
        """Enable or disable the unit display."""
        return await self._run_command("async_set_display", enabled=enabled)

    async def async_set_health_mode(self, *, enabled: bool) -> str | None:
        """Enable or disable health mode."""
        return await self._run_command("async_set_health_mode", enabled=enabled)

    async def async_set_sleep_mode(self, *, enabled: bool) -> str | None:
        """Enable or disable sleep mode."""
        return await self._run_command("async_set_sleep_mode", enabled=enabled)

    async def async_set_turbo_mode(self, *, enabled: bool) -> str | None:
        """Enable or disable turbo mode."""
        return await self._run_command("async_set_turbo_mode", enabled=enabled)

    async def async_set_aux_heat(self, *, enabled: bool) -> str | None:
        """Enable or disable auxiliary heat."""
        return await self._run_command("async_set_aux_heat", enabled=enabled)

    async def async_set_beep(self, *, enabled: bool) -> str | None:
        """Enable or disable command beeps."""
        return await self._run_command("async_set_beep", enabled=enabled)

    async def async_set_feature(self, data_key: str, *, enabled: bool) -> str | None:
        """Set any feature described by the selected protocol profile."""
        return await self._run_command("async_set_feature", data_key, enabled=enabled)

    async def async_set_number(self, data_key: str, value: float) -> str | None:
        """Set any numeric property described by the selected profile."""
        return await self._run_command("async_set_number", data_key, value)

    async def async_send_discovery(self) -> None:
        """Send local device discovery."""
        await self._client.async_send_discovery()

    def update_cloud_token(self, token: str | None) -> None:
        """Update the live cloud token."""
        self._client.update_cloud_token(token)

    async def async_close(self) -> None:
        """Close this device's transport resources."""
        await self._client.async_close()
