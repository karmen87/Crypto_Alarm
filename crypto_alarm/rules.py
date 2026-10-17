"""
Pure alarm logic: input validation and trigger checks. No I/O, clocks or locks, so
everything here can be tested directly.

History is a time-sorted list of (timestamp, price) tuples.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections.abc import Collection, Sequence

from .formatting import SINCE_START
from .models import Alarm, Asset, ExtremeAlarm, TargetAlarm, TimeframeAlarm

DIRECTIONS = {"up", "down", "any"}
EXTREME_TYPES = {"max", "min"}
TIME_UNITS = {"minutes": 60, "hours": 3600, "days": 86400}

# Must stay below Settings.history_retention.
MAX_WINDOW_SECONDS = 7 * 86400
TARGET_TOLERANCE = 0.001  # 'any'-direction target alarms fire on first check within 0.1%

History = Sequence[tuple[float, float]]


# --- validation -----------------------------------------------------------------------


def positive_float(value: object, name: str) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number") from None
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be greater than 0")
    return number


def choice(value: object, allowed: Collection[str], name: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"Invalid {name}")
    return value


def time_value(value: object, unit: str) -> int | None:
    """Validate a timeframe amount; returns None for 'since_start'."""
    if unit == SINCE_START:
        return None
    try:
        amount: int = int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        raise ValueError("Time must be a whole number") from None
    if amount < 1:
        raise ValueError("Time must be at least 1")
    if amount * TIME_UNITS[unit] > MAX_WINDOW_SECONDS:
        raise ValueError("Timeframe cannot exceed 7 days")
    return amount


def window_seconds(alarm: TimeframeAlarm) -> int:
    assert alarm.time_value is not None
    return alarm.time_value * TIME_UNITS[alarm.time_unit]


# --- trigger checks -------------------------------------------------------------------


def check_target(alarm: TargetAlarm, price: float) -> tuple[bool, str | None]:
    """
    Fire when the price crosses the target between two evaluations. On the first
    evaluation (no previous price) also fire if the price is already beyond the
    target, so a freshly created alarm is never silently dead.
    """
    target, prev, direction = alarm.target_price, alarm.prev_price, alarm.direction

    if prev is None:
        if direction == "up":
            return (True, "up") if price >= target else (False, None)
        if direction == "down":
            return (True, "down") if price <= target else (False, None)
        if abs(price - target) / target < TARGET_TOLERANCE:
            return True, "up" if price >= target else "down"
        return False, None

    if direction in ("up", "any") and prev < target <= price:
        return True, "up"
    if direction in ("down", "any") and prev > target >= price:
        return True, "down"
    return False, None


def check_extreme(alarm: ExtremeAlarm, asset: Asset) -> tuple[bool, str | None]:
    """Fire when price is `percentage` below the tracked max / above the tracked min."""
    if alarm.extreme_type == "max":
        peak = asset.max_price
        if peak > 0 and (peak - asset.price) / peak * 100 >= alarm.percentage:
            return True, "down"
    else:
        trough = asset.min_price
        if trough > 0 and (asset.price - trough) / trough * 100 >= alarm.percentage:
            return True, "up"
    return False, None


def price_at(history: History, timestamp: float) -> float | None:
    """Latest sample at or before `timestamp`, or None if history doesn't reach back that far."""
    idx = bisect_right(history, (timestamp, math.inf)) - 1
    return history[idx][1] if idx >= 0 else None


def check_timeframe(
    alarm: TimeframeAlarm, price: float, history: History, now: float
) -> tuple[bool, str | None, float | None]:
    """
    Returns (triggered, direction, start_price).

    'since_start' alarms compare against the stored start price (reset by the monitor
    after each trigger). Windowed alarms compare against the price one full window ago
    and stay silent until history reaches back that far.
    """
    if alarm.time_unit == SINCE_START:
        start = alarm.start_price
    else:
        start = price_at(history, now - window_seconds(alarm))

    if not start:
        return False, None, start

    change = (price - start) / start * 100
    if alarm.direction in ("up", "any") and change >= alarm.percentage:
        return True, "up", start
    if alarm.direction in ("down", "any") and change <= -alarm.percentage:
        return True, "down", start
    return False, None, start


def percent_to_trigger(alarm: Alarm, asset: Asset) -> float | None:
    """How far (in percentage points) the alarm is from firing; None when not computable."""
    price = asset.price
    if not price:
        return None

    if isinstance(alarm, TargetAlarm):
        return (alarm.target_price - price) / price * 100

    if isinstance(alarm, ExtremeAlarm):
        if alarm.extreme_type == "max":
            return alarm.percentage - (asset.max_price - price) / asset.max_price * 100
        return alarm.percentage - (price - asset.min_price) / asset.min_price * 100

    if isinstance(alarm, TimeframeAlarm) and alarm.start_price:
        change = (price - alarm.start_price) / alarm.start_price * 100
        if alarm.direction == "up":
            return alarm.percentage - change
        if alarm.direction == "down":
            return alarm.percentage + change
        return alarm.percentage - abs(change)

    return None
