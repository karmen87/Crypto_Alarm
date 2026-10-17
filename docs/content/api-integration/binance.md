---
title: "Binance Integration"
weight: 1
---

# Binance API Integration

## Overview

The Crypto Price Alarm uses Binance's **public market-data API** to get real-time prices. No API key or authentication is required. All code lives in `crypto_alarm/binance.py`, which contains a small REST client (`BinanceClient`) and a WebSocket price feed (`PriceFeed`).

## API Endpoints

| | Default | Override |
|---|---------|----------|
| **REST base URL** | `https://api.binance.com` | `BINANCE_API_BASE` |
| **WebSocket base URL** | `wss://stream.binance.com:9443` | `BINANCE_WS_BASE` |

{{% notice tip "Where api.binance.com is blocked" %}}
Binance restricts some regions. If the REST calls fail there, point `BINANCE_API_BASE` at Binance's market-data-only host:

```
BINANCE_API_BASE=https://data-api.binance.vision
```
{{% /notice %}}

**REST endpoints used**:

| Endpoint | Used for |
|----------|----------|
| `GET /api/v3/exchangeInfo?symbol=` | validating a pair, reading its base and quote asset and `TRADING` status |
| `GET /api/v3/ticker/24hr?symbols=[...]` | initial price when adding a pair, and the REST fallback (batched) |
| `GET /api/v3/klines` | price history backfill (`1h` and `5m` candles) |

**WebSocket stream**: `/stream?streams=btcusdt@ticker/ethbtc@ticker/...`

## Streaming Architecture

### One Combined Stream

`PriceFeed` opens a **single** WebSocket connection that subscribes to the `<symbol>@ticker` stream of every monitored pair. Each message carries the last price (`c`), the 24-hour change percent (`P`), the 24-hour high (`h`) and low (`l`) and the volume (`v`), and is passed to `Monitor.on_tick`.

```python
streams = "/".join(f"{s.lower()}@ticker" for s in symbols)
ws = websocket.WebSocketApp(f"{ws_base}/stream?streams={streams}", ...)
ws.run_forever(ping_interval=20, ping_timeout=10)
```

### Why a stream instead of polling?

| | Stream | Polling |
|---|--------|---------|
| Latency | updates as they happen | up to the polling interval |
| REST rate limit | none | consumes request weight |
| Efficiency | one connection for all pairs | one request per cycle |

Alarms are evaluated once a second on the latest price, so the stream gives sub-second freshness without spending REST quota.

### Reconnecting

- The feed thread checks once a second
- The connection is re-opened when the **set of pairs changes** (a pair added or removed) or when it **dies**
- After a connect, the next reconnect attempt is delayed by a backoff that starts at 1 s and doubles up to 30 s; it resets to 1 s as soon as a message arrives
- If `websocket-client` is not installed, the feed logs a warning and uses REST polling only

## REST Fallback

If a symbol has had no tick for **15 seconds**, it is polled over REST:

- Polls are batched into **one** `ticker/24hr` request for all stale symbols
- At most one poll every **10 seconds**
- Symbols Binance rejects as invalid are marked dead and retried only every **10 minutes**
- One delisted symbol would make a batch fail, so the client isolates it by retrying symbols one at a time and keeps updating the rest

### Feed Status

`PriceFeed.status()` drives both the header badge and `/healthz`:

| Mode | Condition |
|------|-----------|
| `idle` | no pairs are monitored |
| `stream` | a stream tick arrived within the last 30 s |
| `polling` | no recent stream tick, but a REST poll succeeded within 30 s |
| `connecting` | nothing yet, within 15 s of startup |
| `down` | otherwise |

`/healthz` returns HTTP **503** with `"status": "degraded"` when the mode is `down`.

## Adding a Pair

```
User enters "BTCUSDT"
  ↓
Format check: ^[A-Z0-9]{5,20}$        → "Enter a pair like BTCUSDT or ETHBTC"
  ↓
Already monitored?                    → "Pair already added"
  ↓
exchangeInfo?symbol=BTCUSDT           → base BTC, quote USDT, must be TRADING
  ↓
ticker/24hr?symbols=["BTCUSDT"]       → first price and 24h stats
  ↓
klines backfill (1h + 5m)             → price history for timeframe alarms
  ↓
Pair saved and broadcast to every browser
```

The base and quote assets come from Binance and are **not** parsed out of the symbol text, so every quote Binance supports works.

**Errors shown to the user**:

| Situation | Message |
|-----------|---------|
| unknown or non-trading symbol | "BTCXYZ was not found on Binance (or is not trading). Try BTCUSDT, ETHUSDT, BNBUSDT ..." |
| rate limited | "Binance rate limit hit, retry in Ns" |
| Binance unreachable | "Could not reach Binance (ConnectionError)" |

A rate limit or network failure is reported as such and not as "not found".

## History Backfill

Timeframe alarms need prices from the past, so the server downloads candles:

```python
def get_history(symbol, retention_days=8):
    hourly = get_klines(symbol, "1h", retention_days * 24)   # 192 hourly closes
    recent = get_klines(symbol, "5m", 288)                   # last 24 h of 5-minute closes
    hourly = [p for p in hourly if p[0] < recent[0][0]]      # no overlap
    return hourly + recent
```

- Candles are returned as `(close_time_seconds, close_price)`, and only closed candles are kept
- The backfill runs when a pair is added and for every saved pair at startup, spaced 0.25 s apart
- If it fails, a warning is logged and timeframe alarms on that pair wait for live samples

## Rate Limiting & Resilience

### Error Handling

```python
if resp.status_code in (418, 429):
    retry_after = float(resp.headers.get("Retry-After", 60))
    self._blocked_until = time.time() + retry_after
    raise RateLimited(retry_after)
```

Failure types:

| Exception | Meaning |
|-----------|---------|
| `InvalidSymbol` | Binance error code `-1121`, or the symbol isn't `TRADING` |
| `RateLimited` | HTTP 418 or 429; further requests are refused locally until `Retry-After` passes |
| `NetworkError` | the request could not be sent or timed out (10 s timeout) |
| `BinanceError` | any other rejection or HTTP error |

While a rate limit is active, the client does not call Binance at all; it raises `RateLimited` immediately, which protects against escalating to an IP ban.

### Stale Data Protection

Alarms ignore any price older than **120 seconds**, and the UI marks that pair **stale**. An outage therefore cannot trigger alarms from old data, and you can see at a glance that a pair is not updating.

### Network Failure Recovery

- WebSocket drops reconnect automatically with backoff
- REST polling takes over for silent symbols while the stream is down
- Everything recovers by itself when Binance comes back; no restart is needed

## Notification APIs

Alarm notifications go out through plain HTTP POSTs:

| Channel | Request |
|---------|---------|
| ntfy | `POST {NTFY_SERVER}/{NTFY_TOPIC}` with the message as the body and a `Title: Crypto Alarm` header |
| Telegram | `POST https://api.telegram.org/bot<token>/sendMessage` with `{chat_id, text}` |
| Webhook | `POST {ALARM_WEBHOOK_URL}` with JSON `{"title": "Crypto Alarm", "message": "..."}` |

Each delivery has a 10 s timeout and up to 3 attempts. Repeat messages for one alarm are suppressed for 30 seconds. See [Python App]({{% relref "/implementations/python-app" %}}#notifications-when-no-browser-is-open).

## Troubleshooting

**Header says "Binance feed down" or `/healthz` returns 503**
- Check that the machine can reach `api.binance.com` and `stream.binance.com:9443`
- In regions where Binance is blocked, set `BINANCE_API_BASE=https://data-api.binance.vision`
- Look in the logs for "Binance stream error" and "REST price poll failed"

**"Binance rate limit hit"**
- Wait for the stated number of seconds; the app retries by itself afterward

**A pair stays stale**
- Binance may have delisted the symbol; the log will say "was rejected by Binance; retrying in 600s"

## Next Steps

- See **Alarm Logic** for how prices turn into alarms
- See **DevOps** for deployment and monitoring
