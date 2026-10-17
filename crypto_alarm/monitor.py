"""
Monitor: owns pairs, alarms and price history, and runs the evaluation loop.

Prices arrive through binance.PriceFeed via on_tick(). A once-a-second loop evaluates alarms,
pushes state to the UI, persists data and sends notifications. All shared state is guarded by
one RLock; disk writes and callbacks happen outside it.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

from . import rules
from .binance import SYMBOL_RE, BinanceClient, BinanceError, InvalidSymbol, PriceFeed, Ticker
from .engine import evaluate
from .formatting import SINCE_START
from .models import Alarm, Asset, ExtremeAlarm, TargetAlarm, TimeframeAlarm, TriggerEvent
from .notifier import Notifier
from .settings import Settings
from .store import JsonStore
from .views import alarm_view, asset_view, event_view

log = logging.getLogger(__name__)

StateCallback = Callable[[dict[str, Any]], None]


class Monitor:
    def __init__(
        self,
        settings: Settings,
        client: BinanceClient,
        store: JsonStore,
        notifier: Notifier | None = None,
        on_update: StateCallback | None = None,
        on_trigger: StateCallback | None = None,
    ) -> None:
        self.settings = settings
        self.client = client
        self.store = store
        self.notifier = notifier
        self.on_update = on_update
        self.on_trigger = on_trigger

        self.assets, self.alarms = store.load()
        self.history: dict[
            str, list[tuple[float, float]]
        ] = {}  # rebuilt from klines, not persisted

        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._dirty = False
        self._last_save = 0.0
        self.feed = PriceFeed(client, settings.binance_ws_base, self.symbols, self.on_tick)

    # --- persistence ------------------------------------------------------------------

    def save(self) -> None:
        """Snapshot under the lock, write outside it so slow disks never stall price ticks."""
        with self._lock:
            payload = {
                "assets": {t: a.to_dict() for t, a in self.assets.items()},
                "alarms": {i: a.to_dict() for i, a in self.alarms.items()},
            }
            self._dirty = False
            self._last_save = time.time()
        if not self.store.save(payload):
            self._dirty = True

    # --- pairs ------------------------------------------------------------------------

    def symbols(self) -> list[str]:
        with self._lock:
            return list(self.assets)

    def add_asset(self, pair: str | None) -> dict[str, Any]:
        """Validate `pair` against Binance and track it. ValueError messages are user-facing."""
        symbol = (pair or "").strip().upper()
        if not SYMBOL_RE.match(symbol):
            raise ValueError("Enter a pair like BTCUSDT or ETHBTC")
        with self._lock:
            if symbol in self.assets:
                raise ValueError("Pair already added")

        try:
            info = self.client.get_symbol_info(symbol)
            ticker = self.client.get_tickers([symbol]).get(symbol)
        except InvalidSymbol:
            raise ValueError(
                f"{symbol} was not found on Binance (or is not trading). "
                "Try BTCUSDT, ETHUSDT, BNBUSDT ..."
            ) from None
        except BinanceError as e:
            raise ValueError(str(e)) from e
        if ticker is None:
            raise ValueError(f"No price available for {symbol}")

        samples = self._fetch_history(symbol)
        now = time.time()
        asset = Asset(
            ticker=symbol,
            base=info["base"],
            quote=info["quote"],
            price=ticker["price"],
            change_24h=ticker["change24h"],
            high_24h=ticker["high24h"],
            low_24h=ticker["low24h"],
            last_update=now,
        )
        with self._lock:
            if symbol in self.assets:
                raise ValueError("Pair already added")
            self.assets[symbol] = asset
            self.history[symbol] = [*sorted(samples), (now, asset.price)]
            view = asset_view(asset, now=now, max_age=self.settings.max_price_age)
        self.save()
        return view

    def remove_asset(self, ticker: str | None) -> None:
        with self._lock:
            self.assets.pop(ticker or "", None)
            self.history.pop(ticker or "", None)
            for alarm_id in [i for i, a in self.alarms.items() if a.ticker == ticker]:
                del self.alarms[alarm_id]
        self.save()

    def reset_extremes(self, ticker: str | None) -> None:
        """Restart max/min tracking from the current price."""
        with self._lock:
            asset = self.assets.get(ticker or "")
            if asset is None:
                raise ValueError("Unknown pair")
            asset.max_price = asset.min_price = asset.price
        self.save()

    def _fetch_history(self, symbol: str) -> list[tuple[float, float]]:
        try:
            return self.client.get_history(symbol, self.settings.history_retention // 86400)
        except BinanceError as e:
            log.warning(
                "History backfill for %s failed: %s (timeframe alarms will wait)", symbol, e
            )
            return []

    def _backfill_existing(self) -> None:
        for symbol in self.symbols():
            if self._stop.is_set():
                return
            samples = self._fetch_history(symbol)
            with self._lock:
                if symbol in self.assets:
                    self.history[symbol] = sorted(samples + self.history.get(symbol, []))
            self._stop.wait(0.25)

    # --- prices -----------------------------------------------------------------------

    def on_tick(self, symbol: str, ticker: Ticker, now: float | None = None) -> None:
        now = time.time() if now is None else now
        price = ticker["price"]
        with self._lock:
            asset = self.assets.get(symbol)
            if asset is None:
                return
            asset.price = price
            asset.change_24h = ticker["change24h"]
            asset.high_24h = ticker["high24h"]
            asset.low_24h = ticker["low24h"]
            asset.last_update = now
            if price > asset.max_price:
                asset.max_price = price
                self._dirty = True
            if price < asset.min_price:
                asset.min_price = price
                self._dirty = True

            samples = self.history.setdefault(symbol, [])
            if not samples or now - samples[-1][0] >= self.settings.history_spacing:
                samples.append((now, price))
                cutoff = now - self.settings.history_retention
                drop = 0
                while drop < len(samples) and samples[drop][0] < cutoff:
                    drop += 1
                if drop:
                    del samples[:drop]

    # --- alarms -----------------------------------------------------------------------

    def _add_alarm(self, ticker: str, build: Callable[[str, Asset], Alarm]) -> dict[str, Any]:
        with self._lock:
            asset = self.assets.get(ticker)
            if asset is None:
                raise ValueError("Unknown pair")
            alarm = build(str(uuid.uuid4()), asset)
            self.alarms[alarm.id] = alarm
            view = alarm_view(alarm, asset)
        self.save()
        return view

    def add_target_alarm(
        self, ticker: str, target_price: object, direction: object
    ) -> dict[str, Any]:
        price = rules.positive_float(target_price, "Target price")
        side = rules.choice(direction, rules.DIRECTIONS, "direction")
        return self._add_alarm(
            ticker,
            lambda id_, _: TargetAlarm(id=id_, ticker=ticker, target_price=price, direction=side),
        )

    def add_extreme_alarm(
        self, ticker: str, percentage: object, extreme_type: object
    ) -> dict[str, Any]:
        pct = rules.positive_float(percentage, "Percentage")
        kind = rules.choice(extreme_type, rules.EXTREME_TYPES, "extreme type")
        return self._add_alarm(
            ticker,
            lambda id_, _: ExtremeAlarm(id=id_, ticker=ticker, percentage=pct, extreme_type=kind),
        )

    def add_timeframe_alarm(
        self,
        ticker: str,
        percentage: object,
        direction: object,
        time_value: object,
        time_unit: object,
    ) -> dict[str, Any]:
        pct = rules.positive_float(percentage, "Percentage")
        side = rules.choice(direction, rules.DIRECTIONS, "direction")
        unit = rules.choice(time_unit, {*rules.TIME_UNITS, SINCE_START}, "time unit")
        amount = rules.time_value(time_value, unit)
        return self._add_alarm(
            ticker,
            lambda id_, asset: TimeframeAlarm(
                id=id_,
                ticker=ticker,
                percentage=pct,
                direction=side,
                time_unit=unit,
                time_value=amount,
                start_price=asset.price,
            ),
        )

    def remove_alarm(self, alarm_id: str | None) -> None:
        with self._lock:
            removed = self.alarms.pop(alarm_id or "", None)
        if removed is not None:
            self.save()

    def acknowledge_alarm(self, alarm_id: str | None) -> None:
        """The user saw / dismissed a triggered alarm; stop replaying it to new clients."""
        with self._lock:
            alarm = self.alarms.get(alarm_id or "")
            if alarm is None or alarm.acknowledged is not False:
                return
            alarm.acknowledged = True
        self.save()

    def restart_alarm(self, alarm_id: str | None) -> None:
        """Re-arm a triggered target alarm after the cooldown (handled by the monitor loop)."""
        with self._lock:
            alarm = self.alarms.get(alarm_id or "")
            if alarm is None:
                raise ValueError("Alarm not found")
            if not isinstance(alarm, TargetAlarm):
                raise ValueError("Only target alarms can be restarted")
            alarm.acknowledged = True
            alarm.resetting = True
            alarm.reset_until = time.time() + self.settings.cooldown
        self.save()

    def check_alarms(self, now: float | None = None) -> list[TriggerEvent]:
        """Evaluate every armed alarm once and return the ones that fired."""
        now = time.time() if now is None else now
        events: list[TriggerEvent] = []
        changed = False

        with self._lock:
            for alarm in self.alarms.values():
                asset = self.assets.get(alarm.ticker)
                if asset is None or not asset.price:
                    continue

                if (
                    alarm.reset_until
                    and now >= alarm.reset_until
                    and isinstance(alarm, TargetAlarm)
                ):
                    # Re-arm from the current price so only a *new* crossing fires.
                    alarm.triggered = alarm.resetting = False
                    alarm.reset_until = None
                    alarm.prev_price = asset.price
                    changed = True

                if alarm.triggered:
                    continue
                if now - asset.last_update > self.settings.max_price_age:
                    continue

                result = evaluate(alarm, asset, self.history.get(alarm.ticker, []), now)
                if not result.hit:
                    continue

                if isinstance(alarm, TimeframeAlarm) and alarm.time_unit == SINCE_START:
                    alarm.start_price = asset.price  # repeating alarm: restart the window
                    alarm.last_reset_time = now
                else:
                    alarm.triggered = True
                    alarm.triggered_at = now
                    alarm.acknowledged = False
                alarm.last_message = result.message
                alarm.last_direction = result.direction
                events.append(self._snapshot(alarm, asset))
                changed = True

        if changed:
            self.save()
        return events

    @staticmethod
    def _snapshot(alarm: Alarm, asset: Asset) -> TriggerEvent:
        return TriggerEvent(
            alarm=type(alarm)(**vars(alarm)),
            asset=Asset(**vars(asset)),
            message=alarm.last_message or "",
            direction=alarm.last_direction,
        )

    def get_pending_events(self) -> list[dict[str, Any]]:
        """Triggered alarms nobody has acknowledged yet, for clients that connect later."""
        now = time.time()
        with self._lock:
            return [
                event_view(
                    self._snapshot(a, self.assets[a.ticker]),
                    now=now,
                    max_age=self.settings.max_price_age,
                )
                for a in self.alarms.values()
                if a.triggered and a.acknowledged is False and a.ticker in self.assets
            ]

    # --- state for the UI and health checks -------------------------------------------

    def get_state(self) -> dict[str, Any]:
        now = time.time()
        max_age = self.settings.max_price_age
        with self._lock:
            assets = {t: asset_view(a, now=now, max_age=max_age) for t, a in self.assets.items()}
            alarms = {i: alarm_view(a, self.assets.get(a.ticker)) for i, a in self.alarms.items()}
        return {"assets": assets, "alarms": alarms, "feed": self.feed.status()}

    def health(self) -> dict[str, Any]:
        feed = self.feed.status()
        with self._lock:
            pairs, alarms = len(self.assets), len(self.alarms)
        return {
            "status": "degraded" if feed["mode"] == "down" else "ok",
            "feed": feed,
            "pairs": pairs,
            "alarms": alarms,
        }

    # --- lifecycle --------------------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._stop.is_set():
            return
        self._stop.set()
        self.feed.stop()
        if self._thread:
            self._thread.join(timeout=5)
        self.save()

    def _dispatch(self, event: TriggerEvent) -> None:
        log.info("Alarm triggered: %s", event.message.replace("\n", " | "))
        if self.notifier:
            self.notifier.send(event.message, key=event.alarm.id)
        if self.on_trigger:
            payload = event_view(event, now=time.time(), max_age=self.settings.max_price_age)
            self.on_trigger(payload)

    def _loop(self) -> None:
        log.info("Monitoring started")
        self._backfill_existing()
        self.feed.start()
        last_emit = 0.0
        while not self._stop.is_set():
            now = time.time()
            try:
                for event in self.check_alarms(now):
                    self._dispatch(event)
                if self.on_update and now - last_emit >= self.settings.emit_interval:
                    last_emit = now
                    self.on_update(self.get_state())
                if self._dirty and now - self._last_save >= self.settings.save_interval:
                    self.save()
            except Exception:
                log.exception("Error in monitoring loop")
            self._stop.wait(1)
        log.info("Monitoring stopped")
