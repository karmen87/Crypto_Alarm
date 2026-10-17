"""Evaluates one alarm against the current price and builds its notification text."""

from __future__ import annotations

from dataclasses import dataclass

from . import rules
from .formatting import SINCE_START, describe_window, format_price
from .models import Alarm, Asset, ExtremeAlarm, TargetAlarm, TimeframeAlarm


@dataclass(frozen=True)
class Evaluation:
    hit: bool
    direction: str | None
    message: str


def evaluate(alarm: Alarm, asset: Asset, history: rules.History, now: float) -> Evaluation:
    """
    Check `alarm` against `asset`. Updates the alarm's own bookkeeping (previous price for
    crossing detection, start price shown by the UI) but never its triggered state.
    """
    price, quote, name = asset.price, asset.quote, asset.name
    current = f"Current price: {format_price(price)} {quote}"

    if isinstance(alarm, TargetAlarm):
        hit, direction = rules.check_target(alarm, price)
        alarm.prev_price = price
        message = (
            f"{name} reached your target of {format_price(alarm.target_price)} {quote}\n{current}"
        )
        return Evaluation(hit, direction, message)

    if isinstance(alarm, ExtremeAlarm):
        hit, direction = rules.check_extreme(alarm, asset)
        if alarm.extreme_type == "max":
            what = f"down {alarm.percentage:g}% from its max of {format_price(asset.max_price)}"
        else:
            what = f"up {alarm.percentage:g}% from its min of {format_price(asset.min_price)}"
        return Evaluation(hit, direction, f"{name} is {what} {quote}\n{current}")

    if isinstance(alarm, TimeframeAlarm):
        hit, direction, start = rules.check_timeframe(alarm, price, history, now)
        if alarm.time_unit != SINCE_START:
            alarm.start_price = start  # shown by the UI as "% till trigger"
        change = (price - start) / start * 100 if start else 0.0
        message = f"{name} moved {change:+.2f}% {describe_window(alarm)}\n{current}"
        return Evaluation(hit, direction, message)

    raise TypeError(f"Unsupported alarm type: {type(alarm).__name__}")
