"""Semantic analytical values; numeric zero is never an unavailable value."""

import math
import re
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class MetricState(StrEnum):
    VALUE = "VALUE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"
    INCOMPLETE = "INCOMPLETE"
    ORDER_UNVERIFIED = "ORDER_UNVERIFIED"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


Number = int | float | Decimal
_REASON = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _valid_number(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, Decimal):
        return value.is_finite()
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value)


@dataclass(frozen=True)
class MetricValue:
    state: MetricState
    value: Number | None = None
    unit: str | None = None
    numerator: Number | None = None
    denominator: Number | None = None
    reason: str | None = None

    def __post_init__(self):
        if not isinstance(self.state, MetricState):
            raise ValueError("Invalid MetricValue state")
        if self.state == MetricState.VALUE:
            if not _valid_number(self.value) or self.reason is not None:
                raise ValueError(
                    "VALUE needs a finite number and no unavailable reason"
                )
        elif self.value is not None:
            raise ValueError("Only VALUE may carry a numeric value")
        if self.unit is not None and (
            not isinstance(self.unit, str) or not self.unit.strip()
        ):
            raise ValueError("Unit must be a nonempty string")
        if self.reason is not None and (
            not isinstance(self.reason, str) or not _REASON.fullmatch(self.reason)
        ):
            raise ValueError("Reason must be a machine-readable uppercase code")
        for name in ("numerator", "denominator"):
            number = getattr(self, name)
            if number is not None and (not _valid_number(number) or number < 0):
                raise ValueError(f"{name} must be a finite nonnegative number")
        if self.state == MetricState.VALUE and self.denominator == 0:
            raise ValueError("A numeric value cannot use a zero denominator")
