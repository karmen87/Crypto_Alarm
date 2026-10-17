---
title: "Crypto Price Alarm"
weight: 1
---

# Crypto Price Alarm

A reliable web application for tracking Binance trading pairs and receiving alarm notifications when specific price events occur, in the browser and, optionally, on your phone.

## Project Overview

Crypto Price Alarm is a single Python application:

- **Backend** - Flask + Socket.IO server that streams live prices from Binance, evaluates alarms every second, and keeps your data in a JSON file
- **Browser UI** - dependency-free ES modules that only render what the server sends
- **Notifications** - optional ntfy, Telegram and webhook channels for when no browser tab is open

Because monitoring happens on the server, alarms keep firing even when every browser is closed.

## Core Features

### Trading & Monitoring
- **Trading Pair Support**: Monitor any pair listed on Binance (BTCUSDT, ETHBTC, etc.), validated against Binance's `exchangeInfo`
- **Multi-Pair Tracking**: Monitor multiple trading pairs simultaneously
- **Live Price Updates**: Prices stream over Binance's WebSocket, with an automatic REST fallback
- **Smart Price Formatting**: Automatic decimal precision based on the price, and a `$` prefix for dollar-pegged quotes

### Alarm System
- **Three Alarm Types**:
  1. **Target Price**: Alert when price crosses a specific value (from above, below, or any direction)
  2. **% from Max/Min**: Alert when price falls a certain percentage below its maximum or rises above its minimum
  3. **% Move in Timeframe**: Alert when price moves a certain percentage versus one full window ago (minutes, hours or days, up to 7 days), or since the start price
- **Continuous Alarm Sound**: A pulsing tone that plays until the alarm is dismissed
- **Visual Indicators**: Browser title flashes and a modal dialog appears when an alarm triggers
- **Server-Side Notifications**: ntfy, Telegram or a custom webhook, with duplicate suppression

### Persistence & Design
- **Persistent Storage**: Pairs, alarms and max/min values are saved to a JSON file with atomic writes
- **Live Status Badge**: The header shows whether prices come from the stream, the REST fallback, or are down
- **Clean, Minimal Design**: Light and dark color schemes, keyboard-accessible dialogs

## Quick Start

{{% notice tip "Getting Started in 60 Seconds" %}}
1. Install **Python 3.10 or newer**
2. Clone this repository
3. Run `start.bat` (Windows) or `./start.sh` (macOS / Linux)
4. Open `http://localhost:5000` in your browser
5. Click "Test alarm" to verify sound works
6. Start adding trading pairs!

No API key and no configuration needed.
{{% /notice %}}

### Run it manually

```
pip install -e .
python -m crypto_alarm      # then open http://localhost:5000
```

`start.bat` / `start.sh` do the same thing after creating a virtual environment in `venv/`.

### Run it with Docker

```
docker compose up -d
```

The container serves on `127.0.0.1:5000` with gunicorn (one worker, because state lives in the process) and keeps its data in a named volume. See [Python App]({{% relref "/implementations/python-app" %}}) for details.

## Supported Pairs

Any symbol that Binance reports with status `TRADING`. The base and quote assets are read from Binance, not guessed from the symbol text, so every quote currency Binance offers works (USDT, USDC, FDUSD, BTC, ETH, BNB, EUR, TRY, ...).

A pair is entered as upper-case letters and digits, 5 to 20 characters, with no separator.

## Example Trading Pairs

- `BTCUSDT` - Bitcoin priced in Tether (stablecoin)
- `ETHBTC` - Ethereum priced in Bitcoin
- `BNBETH` - Binance Coin priced in Ethereum
- `SOLUSDC` - Solana priced in USD Coin

## Key Benefits

- **No API Key Needed**: Uses Binance's public market-data API
- **Runs Without a Browser**: Server-side monitoring continues with every tab closed
- **Privacy-First**: Your data stays in a JSON file on your own machine
- **Resilient Feed**: WebSocket stream, REST fallback, and backoff when Binance rate-limits

## Important Tips for Reliable Alarms

{{% notice warning "No Authentication: Keep It on Localhost" %}}
The server binds to `127.0.0.1` by default and has **no login**. Anyone who can reach the port can add, remove and dismiss alarms. Only bind `0.0.0.0` (`CRYPTO_ALARM_HOST`) on a network you trust.
{{% /notice %}}

{{% notice info "Browser Tabs and Sound" %}}
Alarms are evaluated on the server, so a closed or inactive tab never causes a missed alarm. Only the **sound** is played by the browser, and browsers can throttle audio in background tabs.

For alarms you cannot afford to miss, configure a [server-side notification channel]({{% relref "/implementations/python-app" %}}#notifications-when-no-browser-is-open) (ntfy, Telegram or a webhook).

If a trigger happens while no browser is connected, it is shown again, with sound, the next time a browser connects, until someone dismisses it.
{{% /notice %}}

{{% notice info "Best Practices" %}}
**Before setting important alarms**:

1. **Test the alarm sound**: Click the "Test alarm" button to verify audio works
2. **Check system volume**: Alarms play at 60% volume
3. **Check the status badge**: It should say "Live" (or "Live (REST fallback)")
4. **Watch for the stale badge**: Alarms ignore prices older than two minutes
5. **Start conservative**: Test with small thresholds before relying on critical alerts

**Common issues**:
- "Enter a pair like BTCUSDT or ETHBTC" -> Use letters and digits only, no slash or dash
- "... was not found on Binance (or is not trading)" -> Check the symbol on Binance
- "Binance feed down" -> Binance is unreachable or blocked; see the [Binance Integration]({{% relref "/api-integration/binance" %}}) page
- "No alarm sound" -> Click anywhere on the page once (browsers require a gesture) and use the Test alarm button
{{% /notice %}}

## Documentation Structure

Use the navigation menu to explore:

- **Implementations** - Architecture, the Python app, and the browser UI
- **Alarm Logic** - Deep dive into the three alarm types
- **API Integration** - Binance REST and WebSocket integration details
- **DevOps** - CI pipeline, Docker, and documentation publishing
