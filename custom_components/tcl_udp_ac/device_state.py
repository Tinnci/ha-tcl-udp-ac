"""Typed observations and deterministic device-state reconciliation."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
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
OBSERVATION_MAX_AGE_SECONDS = 300.0


def _freeze_value(value: Any) -> Any:
    """Freeze nested protocol containers without retaining caller references."""
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _freeze_value(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    return deepcopy(value)


def _copy_value(value: Any) -> Any:
    """Return ordinary detached containers for HA and compatibility callers."""
    if isinstance(value, Mapping):
        return {key: _copy_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_copy_value(item) for item in value]
    return deepcopy(value)


@dataclass(frozen=True)
class Observation:
    """A partial normalized state update from one source."""

    source: StateSource
    received_at: float
    values: dict[str, Any]
    received_at_utc: datetime | None = None
    requested_at: float | None = None


@dataclass(frozen=True)
class FieldObservation:
    """Provenance of the report that last supplied one field."""

    source: StateSource
    received_at: float
    received_at_utc: datetime | None = None
    requested_at: float | None = None

    @property
    def started_at(self) -> float:
        """Use a cloud request's start to exclude responses already in flight."""
        return self.received_at if self.requested_at is None else self.requested_at


@dataclass(frozen=True)
class DeviceState:
    """Immutable snapshot exposed to Home Assistant."""

    values: Mapping[str, Any] = field(default_factory=dict)
    observations: Mapping[str, FieldObservation] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Isolate nested values and prevent snapshot mutation."""
        object.__setattr__(self, "values", _freeze_value(self.values))
        object.__setattr__(
            self, "observations", MappingProxyType(dict(self.observations))
        )

    def as_dict(self) -> dict[str, Any]:
        """Return an isolated dictionary snapshot."""
        return _copy_value(self.values)

    def observed_since(self, started_at: float) -> dict[str, Any]:
        """Return only fields reported by an observation begun after dispatch."""
        return {
            key: _copy_value(self.values[key])
            for key, observation in self.observations.items()
            if observation.source != StateSource.DERIVED
            and observation.started_at >= started_at
        }

    def fresh_values(self, now: float) -> dict[str, Any]:
        """Return physical reports within the observation freshness window."""
        return {
            key: _copy_value(self.values[key])
            for key, observation in self.observations.items()
            if observation.source != StateSource.DERIVED
            and 0 <= now - observation.received_at <= OBSERVATION_MAX_AGE_SECONDS
        }

    def observed_at(self, *keys: str) -> str | None:
        """Return the oldest required report's UTC receipt time, if known."""
        observations = [self.observations.get(key) for key in keys]
        if not observations or any(
            observation is None
            or observation.source == StateSource.DERIVED
            or observation.received_at_utc is None
            for observation in observations
        ):
            return None
        return min(
            observation.received_at_utc
            for observation in observations
            if observation is not None and observation.received_at_utc is not None
        ).isoformat()


@dataclass(frozen=True)
class _FieldState:
    value: Any
    observation: FieldObservation


class StateReducer:
    """Merge partial observations using per-field time and source precedence."""

    def __init__(self) -> None:
        """Initialize an empty field-level state store."""
        self._fields: dict[str, _FieldState] = {}

    def apply(self, observation: Observation) -> DeviceState:
        """Apply an observation and return the resulting immutable snapshot."""
        provenance = FieldObservation(
            source=observation.source,
            received_at=observation.received_at,
            received_at_utc=observation.received_at_utc,
            requested_at=observation.requested_at,
        )
        for key, value in observation.values.items():
            current = self._fields.get(key)
            if current is not None and not self._should_replace(
                current.observation, provenance
            ):
                continue
            self._fields[key] = _FieldState(
                value=deepcopy(value),
                observation=provenance,
            )
        return self.snapshot()

    @staticmethod
    def _should_replace(current: FieldObservation, incoming: FieldObservation) -> bool:
        if (
            current.source == StateSource.UDP
            and incoming.source == StateSource.CLOUD
            and incoming.received_at - current.received_at <= UDP_FRESHNESS_SECONDS
        ):
            return False
        if incoming.started_at != current.started_at:
            return incoming.started_at > current.started_at
        return _SOURCE_PRIORITY[incoming.source] >= _SOURCE_PRIORITY[current.source]

    def snapshot(self) -> DeviceState:
        """Return the current immutable state snapshot."""
        return DeviceState(
            {key: field.value for key, field in self._fields.items()},
            {key: field.observation for key, field in self._fields.items()},
        )

    def as_dict(self) -> dict[str, Any]:
        """Return the current state as an isolated dictionary."""
        return self.snapshot().as_dict()
