"""Command bundle models for TCL protocol profiles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class VerificationPolicy(StrEnum):
    """How a command transaction should verify device application."""

    NONE = "none"
    STATUS_MATCH = "status_match"


class TransactionOutcome(StrEnum):
    """Result level for a command transaction."""

    APPLIED = "applied"
    CLOUD_ONLY_OR_IGNORED = "cloud_only_or_ignored"
    FAILED = "failed"


class CommandTransport(StrEnum):
    """Transport family required by a command bundle."""

    LEGACY_XML = "legacy_xml"
    TSL_PROPERTY = "tsl_property"


@dataclass(frozen=True)
class TransactionResult:
    """Verification result for a command transaction."""

    intent: str
    outcome: TransactionOutcome
    transport_accepted: bool
    matches: dict[str, str]
    mismatches: dict[str, dict[str, str]]
    status_after: dict[str, Any]


@dataclass(frozen=True)
class CaptureEvidence:
    """Traceability from implementation behavior back to capture evidence."""

    level: str
    source: str
    rationale: str


@dataclass(frozen=True)
class TclCommandBundle:
    """A grouped TCL command payload produced by a protocol profile."""

    intent: str
    payload: dict[str, Any]
    evidence: CaptureEvidence
    requires_power_on: bool
    expected_status: dict[str, Any]
    transport: CommandTransport = CommandTransport.LEGACY_XML
    module_id: str | None = None
    source_type: str | None = None

    def to_command_items(self) -> list[tuple[str, str]]:
        """Convert protocol fields to integration command item names."""
        command_map = {
            "turnOn": "TurnOn",
            "baseMode": "BaseMode",
            "setTemp": "SetTemp",
            "degreeH": "DegreeH",
            "windSpd": "WindSpeed",
            "optSuper": "Opt_super",
            "optECO": "Opt_ECO",
            "optHealthy": "OptHealthy",
            "optSleepMd": "Opt_sleepMode",
            "optHeat": "OptHeat",
            "directH": "WindDirection_H",
            "directV": "WindDirection_V",
            "optSolidWd": "OptSolidWd",
        }
        return [
            (command_map.get(key, key), str(value))
            for key, value in self.payload.items()
        ]


@dataclass(frozen=True)
class TclCommandTransaction:
    """A command payload plus the status projection needed to verify it."""

    intent: str
    payload: dict[str, str]
    evidence: CaptureEvidence
    expected_status_projection: dict[str, Any]
    verification_policy: VerificationPolicy = VerificationPolicy.STATUS_MATCH

    def to_command_items(self) -> list[tuple[str, str]]:
        """Convert payload fields to cloud command item names."""
        return TclCommandBundle(
            intent=self.intent,
            payload=self.payload,
            evidence=self.evidence,
            requires_power_on=False,
            expected_status=self.expected_status_projection,
        ).to_command_items()

    def classify_result(
        self,
        *,
        transport_accepted: bool,
        status_after: dict[str, Any],
    ) -> TransactionResult:
        """Classify a transaction without equating transport success with apply."""
        if not transport_accepted:
            return TransactionResult(
                intent=self.intent,
                outcome=TransactionOutcome.FAILED,
                transport_accepted=False,
                matches={},
                mismatches={},
                status_after=status_after,
            )

        matches: dict[str, str] = {}
        mismatches: dict[str, dict[str, str]] = {}
        if self.verification_policy == VerificationPolicy.STATUS_MATCH:
            for key, expected in self.expected_status_projection.items():
                actual = str(status_after.get(key, "?"))
                expected_str = str(expected)
                if actual == expected_str:
                    matches[key] = actual
                else:
                    mismatches[key] = {
                        "expected": expected_str,
                        "actual": actual,
                    }

        outcome = (
            TransactionOutcome.APPLIED
            if not mismatches
            else TransactionOutcome.CLOUD_ONLY_OR_IGNORED
        )
        return TransactionResult(
            intent=self.intent,
            outcome=outcome,
            transport_accepted=True,
            matches=matches,
            mismatches=mismatches,
            status_after=status_after,
        )
