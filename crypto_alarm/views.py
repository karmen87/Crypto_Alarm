"""JSON-ready views of state for the browser. Display text and derived numbers come from here."""

from __future__ import annotations

from typing import Any

from . import rules
from .formatting import describe_alarm, format_pair_price
from .models import Alarm, Asset, TriggerEvent


def asset_view(asset: Asset, *, now: float, max_age: float) -> dict[str, Any]:
    return {
        **asset.to_dict(),
        "priceText": format_pair_price(asset.price, asset.quote),
        "maxPriceText": format_pair_price(asset.max_price, asset.quote),
        "minPriceText": format_pair_price(asset.min_price, asset.quote),
        "stale": now - asset.last_update > max_age,
    }


def alarm_view(alarm: Alarm, asset: Asset | None) -> dict[str, Any]:
    return {
        **alarm.to_dict(),
        "description": describe_alarm(alarm, asset.quote if asset else ""),
        "percentToTrigger": rules.percent_to_trigger(alarm, asset) if asset else None,
    }


def event_view(event: TriggerEvent, *, now: float, max_age: float) -> dict[str, Any]:
    return {
        "alarm": alarm_view(event.alarm, event.asset),
        "asset": asset_view(event.asset, now=now, max_age=max_age),
        "message": event.message,
        "direction": event.direction,
    }
