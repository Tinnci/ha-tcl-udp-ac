"""Typed observations and deterministic device-state reconciliation."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class StateSource(StrEnum):
    """Origin of a normalized device-state observation."""

    CLOUD = "cloud"
    UDP = "udp"
    DERIVED = "derived"


_SOURCE_PRIORITY = {
    StateSource.DERIVED: 0,
    StateSource.CLOUD: 1,
    StateSource.UDP: 2,
}
UDP_FRESHNESS_SECONDS = 90.0


@dataclass(frozen=True)
class Observation:
    """A partial normalized state update from one source."""

    source: StateSource
    received_at: float
    values: dict[str, Any]


@dataclass(frozen=True)
class DeviceState:
    """Immutable snapshot exposed to Home Assistant."""

    values: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Isolate nested values and prevent snapshot mutation."""
        isolated = deepcopy(dict(self.values))
        object.__setattr__(self, "values", MappingProxyType(isolated))

    def as_dict(self) -> dict[str, Any]:
        """Return an isolated dictionary snapshot."""
        return deepcopy(dict(self.values))


@dataclass(frozen=True)
class _FieldState:
    value: Any
    received_at: float
    source: StateSource


class StateReducer:
    """Merge partial observations using per-field time and source precedence."""

    def __init__(self) -> None:
        """Initialize an empty field-level state store."""
        self._fields: dict[str, _FieldState] = {}

    def apply(self, observation: Observation) -> DeviceState:
        """Apply an observation and return the resulting immutable snapshot."""
        for key, value in observation.values.items():
            current = self._fields.get(key)
            if current is not None and not self._should_replace(current, observation):
                continue
            self._fields[key] = _FieldState(
                value=deepcopy(value),
                received_at=observation.received_at,
                source=observation.source,
            )
        return self.snapshot()

    @staticmethod
    def _should_replace(current: _FieldState, incoming: Observation) -> bool:
        if (
            current.source == StateSource.UDP
            and incoming.source == StateSource.CLOUD
            and incoming.received_at - current.received_at <= UDP_FRESHNESS_SECONDS
        ):
            return False
        if incoming.received_at != current.received_at:
            return incoming.received_at > current.received_at
        return _SOURCE_PRIORITY[incoming.source] >= _SOURCE_PRIORITY[current.source]

    def snapshot(self) -> DeviceState:
        """Return the current immutable state snapshot."""
        return DeviceState({key: field.value for key, field in self._fields.items()})

    def as_dict(self) -> dict[str, Any]:
        """Return the current state as an isolated dictionary."""
        return self.snapshot().as_dict()
