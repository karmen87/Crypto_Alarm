"""
Binance public market-data access: a small REST client plus a WebSocket price feed.

Only unauthenticated market-data endpoints are used, so no API key is needed. The
WebSocket stream does not count against REST request weight; REST is used for validation,
history backfill, and as a fallback when the stream is down.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections.abc import Callable, Sequence
from typing import Any, TypedDict

import requests

log = logging.getLogger(__name__)

SYMBOL_RE = re.compile(r"^[A-Z0-9]{5,20}$")


class BinanceError(Exception):
    """Any failure talking to Binance."""


class InvalidSymbol(BinanceError):
    """The symbol does not exist or is not trading."""


class RateLimited(BinanceError):
    def __init__(self, retry_after: float) -> None:
        super().__init__(f"Binance rate limit hit, retry in {int(retry_after) + 1}s")
        self.retry_after = retry_after


class NetworkError(BinanceError):
    """Binance could not be reached."""


class Ticker(TypedDict):
    price: float
    change24h: float
    high24h: float
    low24h: float
    volume: float


class SymbolInfo(TypedDict):
    base: str
    quote: str


def _parse_ticker(d: dict[str, Any]) -> Ticker:
    return {
        "price": float(d["lastPrice"]),
        "change24h": float(d["priceChangePercent"]),
        "high24h": float(d["highPrice"]),
        "low24h": float(d["lowPrice"]),
        "volume": float(d["volume"]),
    }


class BinanceClient:
    def __init__(self, base_url: str = "https://api.binance.com", timeout: float = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self._blocked_until = 0.0

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        wait = self._blocked_until - time.time()
        if wait > 0:
            raise RateLimited(wait)

        try:
            resp = self.session.get(self.base_url + path, params=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise NetworkError(f"Could not reach Binance ({type(e).__name__})") from e

        if resp.status_code in (418, 429):
            try:
                retry_after = float(resp.headers.get("Retry-After", 60))
            except ValueError:
                retry_after = 60.0
            self._blocked_until = time.time() + retry_after
            log.warning("Binance returned %s, backing off for %.0fs", resp.status_code, retry_after)
            raise RateLimited(retry_after)

        if resp.status_code == 400:
            try:
                code = resp.json().get("code")
            except ValueError:
                code = None
            if code == -1121:
                raise InvalidSymbol("Invalid symbol")
            raise BinanceError(f"Binance rejected the request: {resp.text[:200]}")

        if not resp.ok:
            raise BinanceError(f"Binance error {resp.status_code}: {resp.text[:200]}")

        return resp.json()

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        """Base and quote asset of a tradable symbol. Authoritative, unlike string parsing."""
        data = self._get("/api/v3/exchangeInfo", {"symbol": symbol})
        info = data["symbols"][0]
        if info.get("status") != "TRADING":
            raise InvalidSymbol(f"{symbol} is not currently trading")
        return {"base": info["baseAsset"], "quote": info["quoteAsset"]}

    def get_tickers(self, symbols: Sequence[str]) -> dict[str, Ticker]:
        """24h tickers for many symbols in one request. Invalid symbols are left out."""
        if not symbols:
            return {}
        try:
            data = self._get(
                "/api/v3/ticker/24hr",
                {"symbols": json.dumps(list(symbols), separators=(",", ":"))},
            )
        except InvalidSymbol:
            if len(symbols) == 1:
                raise
            # One delisted symbol fails the whole batch; isolate it so the rest keep updating.
            result: dict[str, Ticker] = {}
            for symbol in symbols:
                try:
                    result.update(self.get_tickers([symbol]))
                except InvalidSymbol:
                    log.warning("%s is no longer a valid Binance symbol", symbol)
            return result
        return {d["symbol"]: _parse_ticker(d) for d in data}

    def get_klines(self, symbol: str, interval: str, limit: int) -> list[tuple[float, float]]:
        """[(close_time_seconds, close_price)] for closed candles."""
        rows = self._get("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
        now = time.time()
        return [(r[6] / 1000.0, float(r[4])) for r in rows if r[6] / 1000.0 <= now]

    def get_history(self, symbol: str, retention_days: int = 8) -> list[tuple[float, float]]:
        """Backfill: hourly candles for older data, 5-minute candles for the last day."""
        hourly = self.get_klines(symbol, "1h", retention_days * 24)
        recent = self.get_klines(symbol, "5m", 288)
        if recent:
            hourly = [p for p in hourly if p[0] < recent[0][0]]
        return hourly + recent


class PriceFeed:
    """
    Streams 24h ticker updates for the wanted symbols and calls on_tick(symbol, ticker).

    Uses one combined WebSocket stream, reconnecting with backoff when the symbol set
    changes or the connection drops. Symbols that haven't ticked recently are polled over
    REST in a single batch; symbols Binance reports as invalid are retried only rarely.
    """

    STALE_AFTER = 15  # seconds without a tick before a symbol is polled over REST
    POLL_INTERVAL = 10  # minimum seconds between REST fallback polls
    DEAD_RETRY = 600  # seconds before retrying a symbol Binance rejected
    HEALTHY_WITHIN = 30  # a tick this recent means the feed is healthy
    CONNECT_GRACE = 15  # seconds after start during which "no ticks yet" is not an error

    def __init__(
        self,
        client: BinanceClient,
        ws_base: str,
        get_symbols: Callable[[], Sequence[str]],
        on_tick: Callable[[str, Ticker], None],
    ) -> None:
        self.client = client
        self.ws_base = ws_base.rstrip("/")
        self.get_symbols = get_symbols
        self.on_tick = on_tick
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._ws: Any = None
        self._ws_thread: threading.Thread | None = None
        self._ws_symbols: list[str] = []
        self._last_tick: dict[str, float] = {}
        self._last_ws_tick = 0.0
        self._last_rest_tick = 0.0
        self._last_poll = 0.0
        self._dead: dict[str, float] = {}
        self._backoff = 1.0
        self._next_connect = 0.0
        self._started_at = 0.0

    def start(self) -> None:
        self._started_at = time.time()
        self._thread = threading.Thread(target=self._run, name="price-feed", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._close_ws()
        if self._thread:
            self._thread.join(timeout=5)

    def status(self) -> dict[str, Any]:
        """mode is one of: idle, connecting, stream, polling, down."""
        now = time.time()
        ws_age = now - self._last_ws_tick if self._last_ws_tick else None
        rest_age = now - self._last_rest_tick if self._last_rest_tick else None

        if not self.get_symbols():
            mode = "idle"
        elif ws_age is not None and ws_age < self.HEALTHY_WITHIN:
            mode = "stream"
        elif rest_age is not None and rest_age < self.HEALTHY_WITHIN:
            mode = "polling"
        elif now - self._started_at < self.CONNECT_GRACE:
            mode = "connecting"
        else:
            mode = "down"

        ages = [a for a in (ws_age, rest_age) if a is not None]
        return {"mode": mode, "lastTickAge": round(min(ages), 1) if ages else None}

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                symbols = sorted(self.get_symbols())
                self._ensure_ws(symbols)
                self._poll_stale(symbols)
            except Exception:
                log.exception("Price feed error")
            self._stop.wait(1)

    def _close_ws(self) -> None:
        ws, self._ws = self._ws, None
        if ws is not None:
            try:
                ws.close()
            except Exception:
                log.debug("Error closing WebSocket", exc_info=True)

    def _ensure_ws(self, symbols: list[str]) -> None:
        changed = symbols != self._ws_symbols
        dead = self._ws_thread is not None and not self._ws_thread.is_alive()
        if not changed and not dead:
            return
        if not changed and time.time() < self._next_connect:
            return

        self._close_ws()
        self._ws_symbols = symbols
        self._ws_thread = None
        if not symbols:
            return

        try:
            import websocket  # websocket-client
        except ImportError:
            log.warning("websocket-client is not installed; using REST polling only")
            return

        streams = "/".join(f"{s.lower()}@ticker" for s in symbols)
        ws = websocket.WebSocketApp(
            f"{self.ws_base}/stream?streams={streams}",
            on_message=self._on_message,
            on_open=lambda _ws: log.info("Binance stream connected (%d symbols)", len(symbols)),
            on_error=lambda _ws, err: log.warning("Binance stream error: %s", err),
        )
        self._ws = ws
        self._ws_thread = threading.Thread(
            target=lambda: ws.run_forever(ping_interval=20, ping_timeout=10),
            name="binance-ws",
            daemon=True,
        )
        self._ws_thread.start()
        # If this connection dies, wait longer before the next attempt.
        self._next_connect = time.time() + self._backoff
        self._backoff = min(self._backoff * 2, 30.0)

    def _on_message(self, _ws: Any, raw: str) -> None:
        try:
            d = json.loads(raw)
            d = d.get("data", d)
            if d.get("e") != "24hrTicker":
                return
            ticker: Ticker = {
                "price": float(d["c"]),
                "change24h": float(d["P"]),
                "high24h": float(d["h"]),
                "low24h": float(d["l"]),
                "volume": float(d["v"]),
            }
            now = time.time()
            self._last_tick[d["s"]] = now
            self._last_ws_tick = now
            self._backoff = 1.0
            self.on_tick(d["s"], ticker)
        except Exception:
            log.exception("Bad stream message")

    def _poll_stale(self, symbols: list[str]) -> None:
        now = time.time()
        if now - self._last_poll < self.POLL_INTERVAL:
            return
        stale = [
            s
            for s in symbols
            if now - self._last_tick.get(s, 0) > self.STALE_AFTER and self._dead.get(s, 0) < now
        ]
        if not stale:
            return
        self._last_poll = now

        try:
            tickers = self.client.get_tickers(stale)
        except InvalidSymbol:
            tickers = {}
        except BinanceError as e:
            log.warning("REST price poll failed: %s", e)
            return

        for symbol, ticker in tickers.items():
            self._dead.pop(symbol, None)
            self._last_tick[symbol] = self._last_rest_tick = time.time()
            self.on_tick(symbol, ticker)

        for symbol in set(stale) - set(tickers):
            log.warning("%s was rejected by Binance; retrying in %ds", symbol, self.DEAD_RETRY)
            self._dead[symbol] = now + self.DEAD_RETRY
