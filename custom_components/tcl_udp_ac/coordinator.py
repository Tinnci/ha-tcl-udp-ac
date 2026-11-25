"""DataUpdateCoordinator for tcl_udp_ac."""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TclUdpApiClientError
from .const import DOMAIN, LOGGER
from .log_utils import log_error

COMMAND_CONFIRMATION_TIMEOUT = 30.0
COMMAND_FOREGROUND_CONFIRMATION_TIMEOUT = 2.5
COMMAND_CONFIRMATION_INTERVAL = 2.0
COMMAND_CONFIRMATION_BACKOFF = (0.35, 0.5, 0.8, 1.2, 1.5, 2.0)
ENERGY_STATS_MIN_INTERVAL = 600.0
COMMAND_EVENT = f"{DOMAIN}_command_result"
COMMAND_REPAIR_ISSUE_ID = "command_not_confirmed"
COMMAND_NOT_SENT_ISSUE_ID = "command_not_sent"

if TYPE_CHECKING:
    from .data import TclUdpConfigEntry


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class TclUdpDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: TclUdpConfigEntry

    @staticmethod
    def _value_matches(expected: Any, actual: Any, tolerance: float = 0.15) -> bool:
        if actual is None:
            return False
        if isinstance(expected, bool):
            return bool(actual) is expected
        try:
            return abs(float(expected) - float(actual)) <= tolerance
        except (TypeError, ValueError):
            return str(actual) == str(expected)

    def _command_matches(
        self,
        expected_status: dict[str, Any],
        status: dict[str, Any],
        status_tolerances: Mapping[str, float] | None = None,
    ) -> bool:
        return all(
            self._value_matches(
                expected, status.get(key), (status_tolerances or {}).get(key, 0.15)
            )
            for key, expected in expected_status.items()
        )

    def _fire_command_event(
        self,
        *,
        command_id: str | None,
        outcome: str,
        intent: str,
        expected_status: dict[str, Any],
        status: dict[str, Any],
        transport_outcome: str = "unknown",
        transport_attempts: dict[str, str] | None = None,
        entity_id: str | None = None,
        context_id: str | None = None,
        status_tolerances: Mapping[str, float] | None = None,
    ) -> None:
        payload = {
            "entry_id": self.config_entry.entry_id,
            "command_id": command_id,
            "intent": intent,
            "outcome": outcome,
            "expected_status": dict(expected_status),
            "status": dict(status),
            "transport_outcome": transport_outcome,
            "transport_attempts": dict(transport_attempts or {}),
            "entity_id": entity_id,
            "context_id": context_id,
            "status_tolerances": dict(status_tolerances or {}),
        }
        self._last_command_result = payload
        hass = getattr(self, "hass", None)
        bus = getattr(hass, "bus", None)
        if bus is None:
            return
        bus.async_fire(COMMAND_EVENT, payload)

    @property
    def last_command_result(self) -> dict[str, Any] | None:
        """Return the latest command outcome for diagnostics."""
        result = getattr(self, "_last_command_result", None)
        return dict(result) if result is not None else None

    def _delete_command_issue(self) -> None:
        hass = getattr(self, "hass", None)
        if hass is None:
            return
        ir.async_delete_issue(hass, DOMAIN, self._command_issue_id)
        ir.async_delete_issue(hass, DOMAIN, self._command_not_sent_issue_id)

    @property
    def _command_issue_id(self) -> str:
        """Return the per-entry Repairs issue identifier."""
        return f"{COMMAND_REPAIR_ISSUE_ID}_{self.config_entry.entry_id}"

    @property
    def _command_not_sent_issue_id(self) -> str:
        """Return the per-entry delivery-failure Repairs issue identifier."""
        return f"{COMMAND_NOT_SENT_ISSUE_ID}_{self.config_entry.entry_id}"

    def _create_command_issue(self) -> None:
        hass = getattr(self, "hass", None)
        if hass is None:
            return
        ir.async_create_issue(
            hass,
            DOMAIN,
            self._command_issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=COMMAND_REPAIR_ISSUE_ID,
        )

    def _create_command_not_sent_issue(self) -> None:
        """Create one stable Repairs issue for a failed transport delivery."""
        hass = getattr(self, "hass", None)
        if hass is None:
            return
        ir.async_create_issue(
            hass,
            DOMAIN,
            self._command_not_sent_issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=COMMAND_NOT_SENT_ISSUE_ID,
        )

    async def async_report_command_delivery_failure(
        self,
        *,
        entity_id: str | None = None,
        context_id: str | None = None,
    ) -> bool:
        """Report a command that no configured transport accepted."""
        runtime = self.config_entry.runtime_data
        session = getattr(runtime, "session", None)
        getter = getattr(session, "last_command_attempt", None)
        attempt = getter() if getter is not None else None
        if not attempt or attempt.get("transport_outcome") != "not_sent":
            return False

        intent = str(attempt.get("intent") or "unknown")
        expected_status = attempt.get("expected_status") or {}
        transport_attempts = attempt.get("transport_attempts") or {}
        log_error(
            LOGGER,
            "command_not_sent",
            intent=intent,
            transport_attempts=transport_attempts,
        )
        self._create_command_not_sent_issue()
        self._fire_command_event(
            command_id=None,
            outcome="not_sent",
            intent=intent,
            expected_status=(
                expected_status if isinstance(expected_status, dict) else {}
            ),
            status=dict(self.data or session.get_last_status() or {}),
            transport_outcome="not_sent",
            transport_attempts=(
                transport_attempts if isinstance(transport_attempts, dict) else {}
            ),
            entity_id=entity_id,
            context_id=context_id,
        )
        return True

    async def _async_fetch_cloud_status_for_update(
        self, client: Any, *, is_confirm_poll: bool
    ) -> None:
        """Fetch cloud status, avoiding retry sleeps on confirmation polls."""
        if not is_confirm_poll:
            await client.async_fetch_cloud_status()
            return
        try:
            await client.async_fetch_cloud_status(retries=0)
        except TypeError:
            await client.async_fetch_cloud_status()

    async def _async_update_data(self) -> Any:
        """Update data via library."""
        # For UDP push-based updates, we return the last known status
        # But we also trigger a SyncStatusReq as a manual poll fallback
        runtime = self.config_entry.runtime_data
        client = getattr(runtime, "session", None) or runtime.client
        is_confirm_poll = getattr(self, "_confirmation_poll_active", 0) > 0
        try:
            await client.async_request_status()
            if client.cloud_enabled:
                await self._async_fetch_cloud_status_for_update(
                    client, is_confirm_poll=is_confirm_poll
                )
            status = client.get_last_status()
        except TclUdpApiClientError:
            if client.cloud_enabled:
                await self._async_fetch_cloud_status_for_update(
                    client, is_confirm_poll=is_confirm_poll
                )
            status = client.get_last_status()

        if not status:
            msg = "No status received from TCL UDP AC"
            raise UpdateFailed(msg)
        if client.cloud_statistics_enabled:
            now_mono = time.monotonic()
            last_stats_at = getattr(self, "_last_stats_fetch_at", None)
            stats: dict[str, Any] | None
            if not is_confirm_poll and (
                last_stats_at is None
                or now_mono - last_stats_at >= ENERGY_STATS_MIN_INTERVAL
            ):
                stats = await client.async_fetch_cloud_energy_statistics()
                if stats:
                    self._cached_energy_statistics = stats
                    self._last_stats_fetch_at = now_mono
            else:
                stats = getattr(self, "_cached_energy_statistics", None)
            if stats:
                merge_derived = getattr(client, "merge_derived", None)
                if merge_derived is not None:
                    status = merge_derived({"energy_statistics": stats})
                else:
                    status = dict(status)
                    status["energy_statistics"] = stats
        return status

    def _get_status_update_event(self) -> asyncio.Event:
        """Return or lazily create the UDP push wake-up event."""
        event = getattr(self, "_status_update_event", None)
        if event is None:
            event = asyncio.Event()
            self._status_update_event = event
        return event

    def _confirmation_tasks(self) -> dict[str, asyncio.Task[Any]]:
        """Return or lazily create the active background confirmation map."""
        tasks = getattr(self, "_background_confirmation_tasks", None)
        if tasks is None:
            tasks = {}
            self._background_confirmation_tasks = tasks
        return tasks

    async def async_cancel_confirmation_tasks(self) -> None:
        """Cancel any active background command confirmation tasks."""
        tasks = getattr(self, "_background_confirmation_tasks", None)
        if not tasks:
            return
        pending_tasks = list(tasks.values())
        tasks.clear()
        for task in pending_tasks:
            task.cancel()
        await asyncio.gather(*pending_tasks, return_exceptions=True)

    async def _async_refresh_for_confirmation(self) -> None:
        """Refresh device status without triggering extra statistics HTTP calls."""
        self._confirmation_poll_active = (
            getattr(self, "_confirmation_poll_active", 0) + 1
        )
        try:
            await self.async_request_refresh()
        finally:
            self._confirmation_poll_active = max(
                0, getattr(self, "_confirmation_poll_active", 1) - 1
            )

    def _read_confirmation_view(
        self, client: Any, started_at: float | None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return full status and confirmation-eligible slice."""
        status = dict(self.data or client.get_last_status() or {})
        snapshot_reader = getattr(client, "state_snapshot", None)
        if snapshot_reader is not None and started_at is not None:
            snapshot = snapshot_reader()
            return snapshot.as_dict(), snapshot.observed_since(started_at)
        return status, status

    async def _async_wait_confirmation_step(self, *, step: float, interval: float) -> None:
        """Sleep up to *step* seconds, waking immediately on UDP push."""
        if interval <= 0:
            await asyncio.sleep(0)
            return
        if step <= 0:
            return
        event = self._get_status_update_event()
        if event.is_set():
            return
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(event.wait(), timeout=step)

    @staticmethod
    def _confirmation_step(interval: float, attempt: int) -> float:
        """Return bounded progressive retry interval for confirmation checks."""
        if interval <= 0:
            return 0.0
        schedule = COMMAND_CONFIRMATION_BACKOFF[
            min(attempt, len(COMMAND_CONFIRMATION_BACKOFF) - 1)
        ]
        return min(interval, schedule)

    def _finalize_confirmation_success(
        self,
        *,
        client: Any,
        command_id: str | None,
        intent: str,
        expected_status: dict[str, Any],
        status: dict[str, Any],
        transport_outcome: str,
        transport_attempts: dict[str, str],
        entity_id: str | None,
        context_id: str | None,
        status_tolerances: dict[str, float],
    ) -> None:
        self._clear_pending_command(client, command_id)
        self._delete_command_issue()
        self._fire_command_event(
            command_id=command_id,
            outcome="applied",
            intent=intent,
            expected_status=expected_status,
            status=status,
            transport_outcome=transport_outcome,
            transport_attempts=transport_attempts,
            entity_id=entity_id,
            context_id=context_id,
            status_tolerances=status_tolerances,
        )

    def _finalize_confirmation_timeout(
        self,
        *,
        client: Any,
        command_id: str | None,
        timeout: float,
        intent: str,
        expected_status: dict[str, Any],
        status: dict[str, Any],
        transport_outcome: str,
        transport_attempts: dict[str, str],
        entity_id: str | None,
        context_id: str | None,
        status_tolerances: dict[str, float],
    ) -> None:
        LOGGER.warning(
            "TCL AC command was not confirmed within %.0fs: "
            "intent=%s expected=%s status=%s",
            timeout,
            intent,
            expected_status,
            status,
        )
        self._clear_pending_command(client, command_id)
        self._create_command_issue()
        self._fire_command_event(
            command_id=command_id,
            outcome="not_confirmed",
            intent=intent,
            expected_status=expected_status,
            status_tolerances=status_tolerances,
            status=status,
            transport_outcome=transport_outcome,
            transport_attempts=transport_attempts,
            entity_id=entity_id,
            context_id=context_id,
        )

    async def _async_continue_confirmation(
        self,
        *,
        client: Any,
        command_id: str | None,
        started_at: float | None,
        deadline: float,
        timeout: float,
        interval: float,
        attempt_start: int,
        intent: str,
        expected_status: dict[str, Any],
        status_tolerances: dict[str, float],
        transport_outcome: str,
        transport_attempts: dict[str, str],
        entity_id: str | None,
        context_id: str | None,
    ) -> None:
        """Continue confirmation in the background after the foreground window."""
        attempt = attempt_start
        status: dict[str, Any] = {}
        while True:
            pending_getter = getattr(client, "pending_command_confirmation", None)
            if pending_getter is not None:
                try:
                    still_pending = pending_getter(command_id)
                except TypeError:
                    still_pending = pending_getter()
                if not still_pending:
                    return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            step = min(remaining, self._confirmation_step(interval, attempt))
            attempt += 1
            await self._async_wait_confirmation_step(step=step, interval=interval)
            if interval > 0:
                self._get_status_update_event().clear()
            await self._async_refresh_for_confirmation()
            status, confirmation_status = self._read_confirmation_view(
                client, started_at
            )
            if self._command_matches(
                expected_status, confirmation_status, status_tolerances
            ):
                self._finalize_confirmation_success(
                    client=client,
                    command_id=command_id,
                    intent=intent,
                    expected_status=expected_status,
                    status=status,
                    transport_outcome=transport_outcome,
                    transport_attempts=transport_attempts,
                    entity_id=entity_id,
                    context_id=context_id,
                    status_tolerances=status_tolerances,
                )
                return

        self._finalize_confirmation_timeout(
            client=client,
            command_id=command_id,
            timeout=timeout,
            intent=intent,
            expected_status=expected_status,
            status=status,
            transport_outcome=transport_outcome,
            transport_attempts=transport_attempts,
            entity_id=entity_id,
            context_id=context_id,
            status_tolerances=status_tolerances,
        )

    async def async_confirm_pending_command(
        self,
        *,
        command_id: str | None = None,
        timeout: float = COMMAND_CONFIRMATION_TIMEOUT,
        interval: float = COMMAND_CONFIRMATION_INTERVAL,
    ) -> bool:
        """
        Refresh until the latest command is reflected in state or times out.

        This confirms device application separately from transport acceptance.
        The result is logged and emitted on Home Assistant's event bus so users
        can build automations without being spammed by notifications.
        """
        runtime = self.config_entry.runtime_data
        client = getattr(runtime, "session", None) or runtime.client
        try:
            pending = client.pending_command_confirmation(command_id)
        except TypeError:
            pending = client.pending_command_confirmation()
        if not pending:
            await self.async_request_refresh()
            return True

        intent = str(pending.get("intent") or "unknown")
        expected_status = pending.get("expected_status") or {}
        status_tolerances = pending.get("status_tolerances") or {}
        transport_outcome = str(pending.get("transport_outcome") or "unknown")
        transport_attempts = pending.get("transport_attempts") or {}
        entity_id = pending.get("entity_id")
        context_id = pending.get("context_id")
        started_at = pending.get("started_at")
        if not isinstance(expected_status, dict) or not expected_status:
            self._clear_pending_command(client, command_id)
            await self.async_request_refresh()
            return True

        hass = getattr(self, "hass", None)
        create_task = getattr(hass, "async_create_task", None)
        can_background = (
            callable(create_task)
            and interval > 0
            and timeout > COMMAND_FOREGROUND_CONFIRMATION_TIMEOUT
        )
        tasks = self._confirmation_tasks()
        if can_background and intent in tasks:
            old_task = tasks.pop(intent, None)
            if old_task is not None and not old_task.done():
                old_task.cancel()

        now_start = time.monotonic()
        deadline = now_start + timeout
        foreground_deadline = (
            min(deadline, now_start + COMMAND_FOREGROUND_CONFIRMATION_TIMEOUT)
            if can_background
            else deadline
        )
        attempt = 0
        status: dict[str, Any] = {}
        while True:
            if interval > 0:
                self._get_status_update_event().clear()
            await self._async_refresh_for_confirmation()
            status, confirmation_status = self._read_confirmation_view(
                client, started_at
            )
            if self._command_matches(
                expected_status, confirmation_status, status_tolerances
            ):
                self._finalize_confirmation_success(
                    client=client,
                    command_id=command_id,
                    intent=intent,
                    expected_status=expected_status,
                    status=status,
                    transport_outcome=transport_outcome,
                    transport_attempts=transport_attempts,
                    entity_id=entity_id,
                    context_id=context_id,
                    status_tolerances=status_tolerances,
                )
                return True

            now = time.monotonic()
            if now >= deadline:
                break

            if can_background and now >= foreground_deadline:
                task = create_task(
                    self._async_continue_confirmation(
                        client=client,
                        command_id=command_id,
                        started_at=started_at,
                        deadline=deadline,
                        timeout=timeout,
                        interval=interval,
                        attempt_start=attempt,
                        intent=intent,
                        expected_status=expected_status,
                        status_tolerances=status_tolerances,
                        transport_outcome=transport_outcome,
                        transport_attempts=transport_attempts,
                        entity_id=entity_id,
                        context_id=context_id,
                    )
                )
                tasks[intent] = task

                def _cleanup_task(completed: asyncio.Task[Any], key: str = intent) -> None:
                    if tasks.get(key) is completed:
                        tasks.pop(key, None)

                task.add_done_callback(_cleanup_task)
                return False

            step = self._confirmation_step(interval, attempt)
            if interval > 0:
                step = min(step, max(0.0, foreground_deadline - now))
            attempt += 1
            await self._async_wait_confirmation_step(step=step, interval=interval)

        self._finalize_confirmation_timeout(
            client=client,
            command_id=command_id,
            timeout=timeout,
            intent=intent,
            expected_status=expected_status,
            status=status,
            transport_outcome=transport_outcome,
            transport_attempts=transport_attempts,
            entity_id=entity_id,
            context_id=context_id,
            status_tolerances=status_tolerances,
        )
        return False

    @staticmethod
    def _clear_pending_command(client: Any, command_id: str | None) -> None:
        """Clear one command while supporting the pre-session client contract."""
        try:
            client.clear_pending_command_confirmation(command_id)
        except TypeError:
            client.clear_pending_command_confirmation()

    async def async_handle_status_update(self, status: dict[str, Any]) -> None:
        """Handle status update from UDP broadcast."""
        # Update coordinator data and notify listeners
        self.async_set_updated_data(status)
        self._get_status_update_event().set()
