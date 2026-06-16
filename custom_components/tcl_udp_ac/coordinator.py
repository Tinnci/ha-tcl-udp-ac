"""DataUpdateCoordinator for tcl_udp_ac."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TclUdpApiClientError
from .const import DOMAIN, LOGGER

COMMAND_CONFIRMATION_TIMEOUT = 30.0
COMMAND_CONFIRMATION_INTERVAL = 2.0
COMMAND_EVENT = f"{DOMAIN}_command_result"
COMMAND_REPAIR_ISSUE_ID = "command_not_confirmed"

if TYPE_CHECKING:
    from .data import TclUdpConfigEntry


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class TclUdpDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: TclUdpConfigEntry

    @staticmethod
    def _value_matches(expected: Any, actual: Any) -> bool:
        if actual is None:
            return False
        if isinstance(expected, bool):
            return bool(actual) is expected
        try:
            return abs(float(expected) - float(actual)) <= 0.15
        except (TypeError, ValueError):
            return str(actual) == str(expected)

    def _command_matches(
        self, expected_status: dict[str, Any], status: dict[str, Any]
    ) -> bool:
        return all(
            self._value_matches(expected, status.get(key))
            for key, expected in expected_status.items()
        )

    def _fire_command_event(
        self,
        *,
        outcome: str,
        intent: str,
        expected_status: dict[str, Any],
        status: dict[str, Any],
    ) -> None:
        hass = getattr(self, "hass", None)
        bus = getattr(hass, "bus", None)
        if bus is None:
            return
        bus.async_fire(
            COMMAND_EVENT,
            {
                "entry_id": self.config_entry.entry_id,
                "intent": intent,
                "outcome": outcome,
                "expected_status": expected_status,
                "status": status,
            },
        )

    def _delete_command_issue(self) -> None:
        hass = getattr(self, "hass", None)
        if hass is None:
            return
        ir.async_delete_issue(hass, DOMAIN, COMMAND_REPAIR_ISSUE_ID)

    def _create_command_issue(self) -> None:
        hass = getattr(self, "hass", None)
        if hass is None:
            return
        ir.async_create_issue(
            hass,
            DOMAIN,
            COMMAND_REPAIR_ISSUE_ID,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=COMMAND_REPAIR_ISSUE_ID,
        )

    async def _async_update_data(self) -> Any:
        """Update data via library."""
        # For UDP push-based updates, we return the last known status
        # But we also trigger a SyncStatusReq as a manual poll fallback
        runtime = self.config_entry.runtime_data
        client = runtime.client
        token_manager = getattr(runtime, "token_manager", None)
        if client.cloud_enabled and token_manager is not None:
            # Refresh the cloud token if near expiry; raises ConfigEntryAuthFailed
            # when reauth is required (HA then prompts the user to log in again).
            await token_manager.async_ensure_fresh_token()
        try:
            await client.async_request_status()
            if client.cloud_enabled:
                await client.async_fetch_cloud_status()
            status = client.get_last_status()
        except TclUdpApiClientError:
            if client.cloud_enabled:
                await client.async_fetch_cloud_status()
            status = client.get_last_status()

        if not status:
            msg = "No status received from TCL UDP AC"
            raise UpdateFailed(msg)
        if client.cloud_statistics_enabled:
            stats = await client.async_fetch_cloud_energy_statistics()
            if stats:
                status = dict(status)
                status["energy_statistics"] = stats
        return status

    async def async_confirm_pending_command(
        self,
        *,
        timeout: float = COMMAND_CONFIRMATION_TIMEOUT,
        interval: float = COMMAND_CONFIRMATION_INTERVAL,
    ) -> bool:
        """
        Refresh until the latest command is reflected in state or times out.

        This confirms device application separately from transport acceptance.
        The result is logged and emitted on Home Assistant's event bus so users
        can build automations without being spammed by notifications.
        """
        client = self.config_entry.runtime_data.client
        pending = client.pending_command_confirmation()
        if not pending:
            await self.async_request_refresh()
            return True

        intent = str(pending.get("intent") or "unknown")
        expected_status = pending.get("expected_status") or {}
        if not isinstance(expected_status, dict) or not expected_status:
            client.clear_pending_command_confirmation()
            await self.async_request_refresh()
            return True

        deadline = time.monotonic() + timeout
        status: dict[str, Any] = {}
        while True:
            await self.async_request_refresh()
            status = dict(self.data or client.get_last_status() or {})
            if self._command_matches(expected_status, status):
                client.clear_pending_command_confirmation()
                self._delete_command_issue()
                self._fire_command_event(
                    outcome="applied",
                    intent=intent,
                    expected_status=expected_status,
                    status=status,
                )
                return True

            if time.monotonic() >= deadline:
                break

            await asyncio.sleep(interval)

        LOGGER.warning(
            "TCL AC command was not confirmed within %.0fs: intent=%s expected=%s status=%s",
            timeout,
            intent,
            expected_status,
            status,
        )
        client.clear_pending_command_confirmation()
        self._create_command_issue()
        self._fire_command_event(
            outcome="not_confirmed",
            intent=intent,
            expected_status=expected_status,
            status=status,
        )
        return False

    async def async_handle_status_update(self, status: dict[str, Any]) -> None:
        """Handle status update from UDP broadcast."""
        # Update coordinator data and notify listeners
        self.async_set_updated_data(status)
