"""Human-readable text for prices and alarms. The browser UI only displays these strings."""

from __future__ import annotations

from .models import Alarm, ExtremeAlarm, TargetAlarm, TimeframeAlarm

SINCE_START = "since_start"
_USD_QUOTES = {"USDT", "USDC", "USD", "BUSD", "FDUSD", "DAI", "TUSD", "USDP"}


def format_price(price: float) -> str:
    if price >= 1000:
        return f"{price:,.2f}"
    if price >= 1:
        return f"{price:.4f}"
    if price >= 0.01:
        return f"{price:.6f}"
    return f"{price:.8f}"


def format_pair_price(price: float, quote: str) -> str:
    """Price as shown in the UI: dollar-pegged quotes get a '$' prefix."""
    text = format_price(price)
    return f"${text}" if quote.upper() in _USD_QUOTES else text


def describe_window(alarm: TimeframeAlarm) -> str:
    if alarm.time_unit == SINCE_START:
        return "since start"
    return f"in {alarm.time_value} {alarm.time_unit}"


def describe_alarm(alarm: Alarm, quote: str) -> str:
    if isinstance(alarm, TargetAlarm):
        suffix = {"up": " (from below)", "down": " (from above)"}.get(alarm.direction, "")
        return f"Target price: {format_pair_price(alarm.target_price, quote)}{suffix}"

    if isinstance(alarm, ExtremeAlarm):
        what = "down from max" if alarm.extreme_type == "max" else "up from min"
        return f"{alarm.percentage:g}% {what} price"

    if isinstance(alarm, TimeframeAlarm):
        move = {"up": "up", "down": "down"}.get(alarm.direction, "change")
        if alarm.time_unit == SINCE_START:
            return f"{alarm.percentage:g}% {move} since start (resets on trigger)"
        return f"{alarm.percentage:g}% {move} in {alarm.time_value} {alarm.time_unit}"

    return "Unknown alarm type"
