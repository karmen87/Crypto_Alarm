---
title: "Crypto Price Alarm"
weight: 1
---

# Crypto Price Alarm

A reliable web application for tracking cryptocurrency trading pairs and receiving alarm notifications when specific price events occur.

## Project Overview

This repository contains two separate implementations of the Crypto Price Alarm:

- **JavaScript App** - Standalone client-side application (no server required)
- **Python App** - Flask-based server application with WebSocket support

Both applications provide the same core functionality but use different technologies. Choose the one that best fits your needs.

## Core Features

### Trading & Monitoring
- **Trading Pair Support**: Monitor any trading pair available on CoinGecko (BTCUSDT, ETHBTC, etc.)
- **Multi-Pair Tracking**: Monitor multiple trading pairs simultaneously
- **Real-Time Price Updates**: Prices update every 15 seconds using CoinGecko API
- **Smart Price Formatting**: Automatic decimal precision based on pair type

### Alarm System
- **Three Alarm Types**:
  1. **Target Price**: Alert when price reaches a specific value (from above, below, or any direction)
  2. **% Change from Max/Min**: Alert when price moves a certain percentage from its maximum or minimum
  3. **% Move in Timeframe**: Alert when price moves a certain percentage within a specified time period
- **Continuous Alarm Sound**: Audible alerts that play until manually dismissed
- **Visual Indicators**: Browser title flashes when alarm triggers

### Persistence & Design
- **Persistent Storage**: All settings and alarms are saved
- **Clean, Minimal Design**: Intuitive interface focused on functionality
- **Reliable Monitoring**: Continuous background monitoring with status indicator

## Quick Start

{{% notice tip "Getting Started in 60 Seconds" %}}
**JavaScript App** (fastest option):
1. Download or clone this repository
2. Navigate to `javascript-app/` folder
3. Double-click `index.html` to open in browser
4. Click "🔔 Test Alarm" to verify sound works
5. Start adding trading pairs!

No installation, no configuration, no server needed.
{{% /notice %}}

### JavaScript App (Recommended for simplicity)

1. Navigate to the `javascript-app/` folder
2. Open `index.html` in your web browser
3. The app will start monitoring immediately

### Python App (For advanced features)

1. Navigate to the `python-app/` folder
2. Follow the instructions in `python-app/PYTHON_SETUP.md`
3. Run the Flask server and access via web browser

## Supported Quote Currencies

USDT, USDC, USD, BUSD, DAI, BTC, ETH, BNB, EUR, GBP

## Example Trading Pairs

- `BTCUSDT` - Bitcoin priced in Tether (stablecoin)
- `ETHBTC` - Ethereum priced in Bitcoin
- `BNBETH` - Binance Coin priced in Ethereum
- `SOLUSDC` - Solana priced in USD Coin

## Key Benefits

- **No API Key Needed**: Uses CoinGecko's free public API
- **Browser-Based**: Works in all modern browsers
- **Privacy-First**: All data stored locally (JavaScript) or on your server (Python)
- **No Installation**: JavaScript version runs directly from HTML file

## Important Tips for Reliable Alarms

{{% notice warning "JavaScript App: Keep Browser Tab Visible" %}}
**For the JavaScript version**: Browsers suspend audio for inactive tabs to save resources.

For reliable alarm sounds:
- ✅ Keep the browser tab **visible** (not minimized)
- ✅ Use a dedicated browser window if monitoring long-term
- ⚠️ If tab is inactive for 5-10+ minutes, alarm sound may not play
- ℹ️ Visual backup: Page title will flash "🚨 ALARM TRIGGERED! 🚨"

**Python version doesn't have this limitation** - server-side monitoring continues even when browser is closed.
{{% /notice %}}

{{% notice info "Best Practices" %}}
**Before setting important alarms**:

1. **Test the alarm sound**: Click "🔔 Test Alarm" button to verify audio works
2. **Check system volume**: Alarms play at 60% volume
3. **Verify pair format**: Must end with supported quote currency (USDT, BTC, ETH, etc.)
4. **Allow time for history**: Timeframe alarms need sufficient price data (e.g., 2-hour alarm needs 2 hours of history)
5. **Start conservative**: Test with small thresholds before relying on critical alerts

**Common issues**:
- "Invalid pair format" → Check quote currency is supported
- "Base asset not found" → Verify token exists on CoinGecko
- "No alarm sound" → Check browser audio permissions, keep tab visible (JS version)
{{% /notice %}}

## Documentation Structure

Use the navigation menu to explore:

- **Implementations** - Detailed comparison of JavaScript vs Python versions
- **Alarm Logic** - Deep dive into the three alarm types
- **API Integration** - CoinGecko API implementation details
- **DevOps** - CI/CD pipeline and automation
