"""Per-device command confirmation tracking."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .command_bundles import CommandReceipt


@dataclass(frozen=True)
class PendingCommand:
    """One independently tracked command expectation."""

    command_id: str
    intent: str
    expected_status: dict[str, Any]
    transport_outcome: str
    transport_attempts: dict[str, str]
    created_at: float

    def as_dict(self) -> dict[str, Any]:
        """Return the compatibility dictionary used by existing callers."""
        return {
            "command_id": self.command_id,
            "intent": self.intent,
            "expected_status": dict(self.expected_status),
            "transport_outcome": self.transport_outcome,
            "transport_attempts": dict(self.transport_attempts),
            "created_at": self.created_at,
        }


class CommandTracker:
    """Track multiple pending commands without overwriting prior commands."""

    def __init__(self) -> None:
        """Initialize an empty per-device tracker."""
        self._sequence = 0
        self._pending: dict[str, PendingCommand] = {}

    def record(self, receipt: CommandReceipt) -> str:
        """Record one command expectation and return its stable identifier."""
        self._sequence += 1
        command_id = f"cmd-{self._sequence}"
        self._pending[command_id] = PendingCommand(
            command_id=command_id,
            intent=receipt.intent,
            expected_status=dict(receipt.expected_status),
            transport_outcome=receipt.delivery.outcome,
            transport_attempts=receipt.delivery.as_dict(),
            created_at=time.time(),
        )
        return command_id

    def pending(self, command_id: str | None = None) -> PendingCommand | None:
        """Return a specific command, or the latest pending command for compatibility."""
        if command_id is not None:
            return self._pending.get(command_id)
        if not self._pending:
            return None
        return next(reversed(self._pending.values()))

    def complete(self, command_id: str) -> PendingCommand | None:
        """Remove and return a completed command."""
        return self._pending.pop(command_id, None)

    def clear(self) -> None:
        """Clear every pending command."""
        self._pending.clear()
