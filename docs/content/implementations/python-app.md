---
title: "Python App"
weight: 1
---

# Python App: Server-Side Implementation

## Overview

The Python app is a Flask + Socket.IO server that streams prices from Binance, evaluates alarms every second, persists everything to a JSON file and optionally pushes notifications to your phone. It is started with `python -m crypto_alarm` (package `crypto_alarm/`) or served by gunicorn in Docker.

## Architecture

### Core Components

```
crypto_alarm/
├── __main__.py     # Entry point: python -m crypto_alarm
├── web.py          # Flask app factory, Socket.IO events, /healthz
├── monitor.py      # Pairs, alarms, history, evaluation loop
├── binance.py      # BinanceClient (REST) + PriceFeed (WebSocket)
├── rules.py        # Pure validation and trigger checks
├── engine.py       # Evaluates one alarm, builds notification text
├── models.py       # Asset / Alarm dataclasses and JSON mapping
├── formatting.py   # Price and alarm display text
├── views.py        # JSON views sent to the browser
├── store.py        # Atomic JSON persistence
├── notifier.py     # ntfy / Telegram / webhook delivery
├── settings.py     # Environment-based configuration
├── logs.py         # Text or JSON logging
├── templates/      # index.html
└── static/         # css/, js/ (ES modules), vendor/socket.io.min.js
```

### Technology Stack

- **Flask 3** - HTTP server and templating
- **Flask-SocketIO 5** - real-time communication, `threading` async mode (no eventlet/gevent)
- **websocket-client** - Binance WebSocket stream
- **requests** - Binance REST calls and notification delivery
- **gunicorn** - production server (`gthread` worker class), optional `server` extra
- **Python 3.10+**

### Threads

| Thread | Purpose |
|--------|---------|
| `monitor` | once-a-second loop: evaluate alarms, push state, save |
| `price-feed` | keeps the WebSocket alive, polls over REST when ticks go stale |
| `binance-ws` | runs the WebSocket client |
| `notify-*` | short-lived, one per channel per notification |

## Data Persistence: JSON File Storage

Pairs, alarms and max/min prices are stored in one JSON file. The default location is `data/crypto_data_binance.json` inside the project (anchored to the project folder, not the working directory). Override it with `CRYPTO_ALARM_DATA`. In Docker it is `/data/crypto_data_binance.json` on a named volume.

### Storage Schema

JSON keys are camelCase because the browser UI and the data file share the same names.

```json
{
  "assets": {
    "BTCUSDT": {
      "ticker": "BTCUSDT",
      "base": "BTC",
      "quote": "USDT",
      "price": 50000.0,
      "change24h": 1.2,
      "high24h": 51000.0,
      "low24h": 49000.0,
      "maxPrice": 52000.0,
      "minPrice": 48000.0,
      "lastUpdate": 1760745600.0
    }
  },
  "alarms": {
    "3f2c...": {
      "type": "target",
      "id": "3f2c...",
      "ticker": "BTCUSDT",
      "createdAt": 1760745600.0,
      "triggered": false,
      "triggeredAt": null,
      "acknowledged": null,
      "resetting": false,
      "resetUntil": null,
      "lastMessage": null,
      "lastDirection": null,
      "targetPrice": 55000.0,
      "direction": "up",
      "prevPrice": 50000.0
    }
  }
}
```

Alarm types add their own fields: `extreme` has `percentage` and `extremeType`; `timeframe` has `percentage`, `direction`, `timeUnit`, `timeValue`, `lastResetTime` and `startPrice`.

**Price history is not stored.** It is rebuilt from Binance candles when a pair is added and when the server starts (see [Binance Integration]({{% relref "/api-integration/binance" %}})).

### When Data Is Saved

- **Immediately** on every user action (add or remove a pair or alarm, reset max/min, acknowledge, restart) and whenever an alarm triggers
- **Every 30 seconds at most** for new max/min prices, which change constantly
- **On shutdown** (SIGTERM and Ctrl+C both unwind cleanly so the monitor can save)

### Safety

- **Atomic writes**: data is written to a `.tmp` file, flushed and `fsync`ed, then moved over the real file, so a crash mid-save can never leave a truncated file
- **Corrupt file handling**: an unreadable file is moved to `crypto_data_binance.json.corrupt` and the app starts empty instead of crashing
- **Tolerant loading**: an individual unreadable pair or alarm is skipped with a warning rather than discarding the whole file

### JSON Storage Considerations

- A single process owns the file, so do not run two instances against the same data file
- Back it up by copying the file (or the Docker volume)

## Socket.IO Communication

### Real-Time Updates Architecture

```
Browser A ─┐                                    ┌─ Binance WebSocket
Browser B ─┼── Socket.IO ──  Flask server  ─────┤
Browser C ─┘                 (Monitor loop)     └─ Binance REST
```

All browsers see the same state. Actions from one browser (adding a pair, creating an alarm) are broadcast to every connected browser.

### Events: Browser to Server

| Event | Payload | Effect |
|-------|---------|--------|
| `add_asset` | `{pair}` | validate on Binance and start tracking |
| `remove_asset` | `{ticker}` | stop tracking; also deletes that pair's alarms |
| `reset_extremes` | `{ticker}` | restart max/min tracking from the current price |
| `add_alarm` | `{type, ticker, ...}` | create a `target`, `extreme` or `timeframe` alarm |
| `remove_alarm` | `{alarmId}` | delete an alarm |
| `restart_alarm` | `{alarmId}` | re-arm a triggered target alarm after a cooldown |
| `ack_alarm` | `{alarmId}` | mark a trigger as seen |

`add_alarm` fields by type:

| Type | Fields |
|------|--------|
| `target` | `targetPrice`, `direction` (`up` / `down` / `any`) |
| `extreme` | `percentage`, `extremeType` (`max` / `min`) |
| `timeframe` | `percentage`, `direction`, `timeValue`, `timeUnit` (`minutes` / `hours` / `days` / `since_start`) |

### Events: Server to Browser

| Event | When |
|-------|------|
| `initial_state` | on connect: all pairs, alarms and the feed status |
| `price_update` | every 2 seconds, with the full state |
| `asset_added`, `asset_removed` | a pair was added or removed |
| `alarm_added`, `alarm_removed`, `alarm_restarted` | alarm changes |
| `alarm_triggered` | an alarm fired (also replayed on connect if nobody dismissed it) |
| `error` | a user-facing error message, e.g. "Pair already added" |

### Server-Side Handling

```python
# web.py: user mistakes become error events, bugs are logged
@handler("add_asset")
def add_asset(data):
    emit("asset_added", {"asset": monitor.add_asset(data.get("pair"))}, broadcast=True)
```

Validation errors (`ValueError`) go back to the client as `error` events with a message safe to display. Unexpected exceptions are logged with a traceback and the client only sees "Internal server error".

### Replay of Missed Triggers

A triggered alarm stays `acknowledged: false` until a browser dismisses it (`ack_alarm`). Every browser that connects receives those unacknowledged triggers again, so an alarm that fired while nobody was watching is not lost.

## Background Monitoring

### The Monitor Loop

The `monitor` thread runs once a second:

```python
while not stopped:
    for event in check_alarms(now):      # evaluate every armed alarm
        dispatch(event)                  # notifications + alarm_triggered
    if now - last_emit >= 2.0:
        on_update(get_state())           # price_update to all browsers
    if dirty and now - last_save >= 30:
        save()                           # max/min changes
    wait(1)
```

An exception inside an iteration is logged and the loop carries on.

### Startup

1. Load pairs and alarms from the JSON file
2. Backfill price history for every saved pair from Binance candles (spaced 0.25 s apart to stay polite)
3. Start the price feed
4. Begin the loop

### Server-Side Benefits

- Monitoring continues when every browser is closed
- One Binance connection serves any number of browsers
- Alarm state survives restarts
- Notifications reach you through channels that don't need a tab

## API Integration

Prices come from Binance's public market-data API: a combined WebSocket ticker stream, with REST for validation, history and as a fallback. No API key is needed. See [Binance Integration]({{% relref "/api-integration/binance" %}}) for the full details.

## Notifications When No Browser Is Open

Server-side notifications are sent when an alarm triggers, regardless of whether a browser is connected. Each channel is enabled by environment variables:

| Channel | Variables |
|---------|-----------|
| ntfy | `NTFY_TOPIC` (optional `NTFY_SERVER`, default `https://ntfy.sh`) |
| Telegram | `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` |
| Webhook | `ALARM_WEBHOOK_URL` (receives JSON `{"title", "message"}`) |

Behavior:
- Delivery is fire-and-forget on a background thread per channel, so a slow channel never blocks monitoring
- Failed deliveries are retried up to 3 times with growing delays
- Repeat notifications for the same alarm within 30 seconds are suppressed (this matters for repeating "since start" alarms)
- Failures are logged by exception type only, because request errors embed the URL and Telegram's URL contains the bot token

At startup the log says which channels are active, or "none configured (browser only)".

## Configuration

Everything is configured through environment variables. The app reads the real environment and does **not** load `.env` itself; export the variables, or use `docker compose` (which reads `.env` through `env_file`). `.env.example` documents all of them.

### Web server

| Variable | Default | Meaning |
|----------|---------|---------|
| `CRYPTO_ALARM_HOST` | `127.0.0.1` | bind address |
| `CRYPTO_ALARM_PORT` | `5000` | port |
| `CRYPTO_ALARM_ALLOWED_ORIGINS` | none | extra Socket.IO origins, comma-separated (same origin is always allowed) |
| `CRYPTO_ALARM_SECRET_KEY` | random per start | Flask secret key |
| `CRYPTO_ALARM_LOG_JSON` | off | `1` for one JSON object per log line |

### Storage and Binance

| Variable | Default | Meaning |
|----------|---------|---------|
| `CRYPTO_ALARM_DATA` | `<project>/data/crypto_data_binance.json` | data file |
| `BINANCE_API_BASE` | `https://api.binance.com` | REST host; use `https://data-api.binance.vision` where the main host is blocked |
| `BINANCE_WS_BASE` | `wss://stream.binance.com:9443` | WebSocket host |

### Built-in tuning (not environment-configurable)

| Setting | Value | Meaning |
|---------|-------|---------|
| `max_price_age` | 120 s | alarms ignore older prices; the UI marks the pair stale |
| `cooldown` | 60 s | how long a restarted target alarm stays disarmed |
| `emit_interval` | 2 s | time between `price_update` pushes |
| `save_interval` | 30 s | time between saves of max/min changes |
| `notify_min_interval` | 30 s | per-alarm minimum between notifications |
| `history_spacing` | 30 s | minimum gap between stored history samples |
| `history_retention` | 8 days | how much price history is kept |

## Deployment

### Local Development

```bash
# Windows
start.bat
# macOS / Linux
./start.sh

# or manually
pip install -e .
python -m crypto_alarm

# Access at http://localhost:5000
```

The development entry point runs Flask-SocketIO's built-in Werkzeug server with `allow_unsafe_werkzeug=True`, bound to `127.0.0.1`.

### Production Deployment Options

#### Option 1: Docker (recommended)

```bash
docker compose up -d
```

```yaml
# docker-compose.yml
services:
  crypto-alarm:
    build: .
    ports:
      - "127.0.0.1:5000:5000"   # localhost only; there is no authentication
    volumes:
      - alarm-data:/data
    env_file:
      - path: .env
        required: false
    restart: unless-stopped

volumes:
  alarm-data:
```

The image is built on `python:3.12-slim`:
- Dependencies are installed from `requirements.lock` first, so that layer is cached until the pins change
- The app runs as a non-root `app` user, and `/data` is a volume
- `CRYPTO_ALARM_HOST=0.0.0.0` and `CRYPTO_ALARM_LOG_JSON=1` are set inside the container (the compose file only publishes the port on localhost)
- A `HEALTHCHECK` calls `/healthz` every 30 seconds

#### Option 2: gunicorn

```bash
pip install -e ".[server]"
gunicorn -k gthread -w 1 --threads 100 -b 127.0.0.1:5000 'crypto_alarm.web:create_app()'
```

{{% notice warning "Always use exactly one worker" %}}
Pairs, alarms and price history live in the process. Two workers would each have their own copy, their own Binance connection and would each fire notifications. Scale with `--threads`, not `--workers`.
{{% /notice %}}

Put a reverse proxy (nginx, Caddy) with authentication in front of it if it needs to be reachable from outside; the app has no login of its own. The proxy must pass WebSocket upgrades for `/socket.io/`, and any extra origin must be listed in `CRYPTO_ALARM_ALLOWED_ORIGINS`.

#### Option 3: Systemd Service

```ini
# /etc/systemd/system/crypto-alarm.service
[Unit]
Description=Crypto Price Alarm
After=network-online.target

[Service]
User=cryptoalarm
WorkingDirectory=/opt/crypto-alarm
Environment=CRYPTO_ALARM_DATA=/var/lib/crypto-alarm/crypto_data_binance.json
ExecStart=/opt/crypto-alarm/venv/bin/gunicorn -k gthread -w 1 --threads 100 -b 127.0.0.1:5000 'crypto_alarm.web:create_app()'
Restart=always

[Install]
WantedBy=multi-user.target
```

## Logging & Monitoring

### Application Logging

Logs go to stderr. By default they are readable text:

```
2026-10-18 00:42:22,496 INFO crypto_alarm.monitor: Monitoring started
2026-10-18 00:42:22,497 INFO crypto_alarm: Crypto Price Alarm (Binance) on http://127.0.0.1:5000
```

With `CRYPTO_ALARM_LOG_JSON=1` (the Docker default) each line is one JSON object with `time`, `level`, `logger`, `message` and, for errors, `exception`.

### Alarm Trigger Logging

Every trigger is logged at INFO level with the message flattened to one line:

```
INFO crypto_alarm.monitor: Alarm triggered: BTC/USDT reached your target of 55,000.00 USDT | Current price: 55,010.20 USDT
```

### Health Endpoint

`GET /healthz` returns the feed state and counts, and responds **503** when the price feed is down:

```json
{"status": "ok", "feed": {"mode": "stream", "lastTickAge": 0.4}, "pairs": 3, "alarms": 5}
```

`feed.mode` is one of `idle` (no pairs), `connecting`, `stream`, `polling` (REST fallback) or `down`. The Docker healthcheck uses this endpoint.

## Advantages

- ✅ Monitoring continues when no browser is open
- ✅ Real-time updates for every connected browser
- ✅ Notifications through ntfy, Telegram or a webhook
- ✅ Atomic persistence that survives crashes and restarts
- ✅ Typed, tested alarm logic separated from I/O
- ✅ Docker image with health check and non-root user

## Limitations

- ❌ Requires Python 3.10+ (or Docker)
- ❌ One process only; no horizontal scaling
- ❌ No authentication, so it must stay on a trusted network or behind a proxy
- ❌ Price history is not persisted; it is re-downloaded from Binance at startup
- ❌ Prices only come from Binance, so pairs not listed there cannot be tracked

## Use Cases

- A personal always-on price watcher on a home server, Raspberry Pi or small VPS
- Phone alerts through ntfy or Telegram while the laptop is closed
- Feeding alarm events into other tools through the webhook channel
- A shared dashboard for a household or small team on a trusted network

## Performance Considerations

### Memory Usage

Each pair keeps up to 8 days of history at 30-second spacing, about 23,000 samples at most, which is a few MB per pair.

### Concurrent Clients

The server uses threads rather than an async framework. gunicorn is configured with 100 threads, which is plenty for personal or small-team use. Every client receives the same full-state push every 2 seconds.

### API Rate Limits

The WebSocket stream does not count against Binance's REST limits, and ticker data for all pairs is fetched in one batched REST call when the fallback is needed. On HTTP 418 or 429 the client honors `Retry-After` and stops calling until it passes. See [Binance Integration]({{% relref "/api-integration/binance" %}}).

## Security Considerations

### Network Exposure

```bash
# Default: reachable from this machine only
CRYPTO_ALARM_HOST=127.0.0.1
```

There is no authentication. Do not bind `0.0.0.0` on an untrusted network; if remote access is needed, use a reverse proxy that adds authentication or a VPN.

### Secrets

```bash
# Keep these in the environment, never in the repository
export TELEGRAM_BOT_TOKEN=...
export ALARM_WEBHOOK_URL=...
```

`.env` is git-ignored. The token and webhook URL are excluded from the settings `repr`, and delivery errors are logged by type only so the Telegram token never reaches the logs.

### CORS Configuration

Socket.IO accepts same-origin connections only. To serve the UI from a different origin (for example behind a proxy on another hostname), list it explicitly:

```bash
CRYPTO_ALARM_ALLOWED_ORIGINS=https://alarm.example.com
```

### Input Validation

All input is validated on the server: symbols must match `[A-Z0-9]{5,20}` and exist on Binance, numbers must be finite and greater than 0, directions and units must be from fixed sets, and timeframes cannot exceed 7 days.

## Next Steps

- See **Browser UI** for how alarms are presented
- Explore **Alarm Logic** for the three alarm types
- Check **API Integration** for the Binance details
