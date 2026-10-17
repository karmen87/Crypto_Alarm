"""Typed state objects. JSON keys stay camelCase: the browser UI and saved data files use them."""

from __future__ import annotations

import time
from dataclasses import dataclass, field, fields
from typing import Any, ClassVar


def _camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part.capitalize() for part in tail)


def _to_json(obj: Any) -> dict[str, Any]:
    return {_camel(f.name): getattr(obj, f.name) for f in fields(obj)}


def _from_json(cls: type, data: dict[str, Any]) -> dict[str, Any]:
    """Pick the keys that belong to `cls`, ignoring derived or unknown ones."""
    by_json_key = {_camel(f.name): f.name for f in fields(cls)}
    return {by_json_key[k]: v for k, v in data.items() if k in by_json_key}


@dataclass(kw_only=True)
class Asset:
    ticker: str
    base: str
    quote: str
    price: float
    change_24h: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0
    max_price: float = 0.0  # highest price seen since the pair was added / extremes were reset
    min_price: float = 0.0
    last_update: float = 0.0

    def __post_init__(self) -> None:
        self.max_price = self.max_price or self.price
        self.min_price = self.min_price or self.price

    @property
    def name(self) -> str:
        return f"{self.base}/{self.quote}"

    def to_dict(self) -> dict[str, Any]:
        return {**_to_json(self), "name": self.name}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Asset:
        return cls(**_from_json(cls, data))


@dataclass(kw_only=True)
class Alarm:
    kind: ClassVar[str] = ""

    id: str
    ticker: str
    created_at: float = field(default_factory=time.time)
    triggered: bool = False
    triggered_at: float | None = None
    acknowledged: bool | None = None  # False while a trigger is waiting to be seen
    resetting: bool = False
    reset_until: float | None = None
    last_message: str | None = None
    last_direction: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {**_to_json(self), "type": self.kind}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Alarm:
        try:
            cls = ALARM_TYPES[data["type"]]
        except KeyError:
            raise ValueError(f"Unknown alarm type: {data.get('type')!r}") from None
        return cls(**_from_json(cls, data))


@dataclass(kw_only=True)
class TargetAlarm(Alarm):
    kind: ClassVar[str] = "target"

    target_price: float
    direction: str  # 'up' | 'down' | 'any'
    prev_price: float | None = None  # price at the previous evaluation, for crossing detection


@dataclass(kw_only=True)
class ExtremeAlarm(Alarm):
    kind: ClassVar[str] = "extreme"

    percentage: float
    extreme_type: str  # 'max' | 'min'


@dataclass(kw_only=True)
class TimeframeAlarm(Alarm):
    kind: ClassVar[str] = "timeframe"

    percentage: float
    direction: str
    time_unit: str  # 'minutes' | 'hours' | 'days' | 'since_start'
    time_value: int | None = None
    last_reset_time: float = field(default_factory=time.time)
    start_price: float | None = None


ALARM_TYPES: dict[str, type[Alarm]] = {
    cls.kind: cls for cls in (TargetAlarm, ExtremeAlarm, TimeframeAlarm)
}


@dataclass
class TriggerEvent:
    """Snapshot of an alarm at the moment it fired."""

    alarm: Alarm
    asset: Asset
    message: str
    direction: str | None
