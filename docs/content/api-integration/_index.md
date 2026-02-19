---
title: "API Integration"
weight: 4
chapter: true
---

# API Integration

## Overview

The Crypto Price Alarm integrates with external APIs to fetch real-time cryptocurrency price data. This section documents the API integration strategy, polling mechanisms, and technical implementation details.

## CoinGecko: Primary Data Source

All price data is sourced from **CoinGecko's free public API**, which provides:

- **No Authentication**: No API keys required
- **Comprehensive Coverage**: 10,000+ cryptocurrencies
- **Reliable Uptime**: Industry-standard availability
- **Free Tier**: 50 calls/minute (sufficient for most use cases)

## Key Topics

### Polling Architecture
- 15-second update intervals
- Background job scheduling
- Efficient batching strategies

### Price Calculation
- Stablecoin pairs (BTCUSDT, ETHUSDC)
- Crypto-to-crypto pairs (ETHBTC, BNBETH)
- Ratio calculations and USD proxies

### Rate Limiting & Resilience
- Error handling and retry logic
- Exponential backoff strategies
- Network failure recovery

### Performance Optimization
- Request batching for multiple pairs
- In-memory caching (15s TTL)
- Latency monitoring

## Next Steps

Dive into the **CoinGecko Integration** documentation for complete implementation details.
