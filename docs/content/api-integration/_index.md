---
title: "API Integration"
weight: 4
chapter: true
---

# API Integration

## Overview

The Crypto Price Alarm integrates with external APIs to fetch real-time cryptocurrency price data and to deliver notifications. This section documents the data source, the streaming and fallback mechanisms, and the resilience behavior.

## Binance: Primary Data Source

All price data is sourced from **Binance's public market-data API**, which provides:

- **No Authentication**: No API keys required, only unauthenticated market-data endpoints are used
- **Comprehensive Coverage**: Every spot trading pair Binance lists
- **Real-Time Data**: A WebSocket ticker stream pushes updates as trades happen
- **Free**: The WebSocket stream does not count against REST request weight

## Key Topics

### Streaming Architecture
- One combined WebSocket stream for all monitored pairs
- Automatic reconnect with backoff
- The stream is re-opened when the set of pairs changes

### Price Data
- 24-hour ticker: last price, 24h change, 24h high and low
- No ratio calculations: every pair is a native Binance symbol, so `ETHBTC` is the exchange's own price
- Base and quote assets come from Binance's `exchangeInfo`

### History Backfill
- Hourly and 5-minute candles download when a pair is added and at startup
- Enables timeframe alarms of up to 7 days immediately

### Rate Limiting & Resilience
- REST fallback when the stream is silent
- `Retry-After` handling for HTTP 418 / 429
- Isolation of delisted symbols
- A health endpoint and a status badge in the UI

### Notification APIs
- ntfy, Telegram and webhook delivery with retries and duplicate suppression

## Next Steps

Dive into the **Binance Integration** documentation for complete implementation details.
