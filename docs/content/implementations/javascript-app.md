---
title: "JavaScript App"
weight: 1
---

# JavaScript App: Client-Side Implementation

## Overview

The JavaScript implementation is a pure client-side application requiring zero installation or server infrastructure. It runs entirely in the browser using vanilla JavaScript, HTML, and CSS.

## Architecture

### Core Components

```
javascript-app/
├── index.html          # UI structure + inline CSS
├── app.js              # Application logic
├── alarm.mp3           # Alarm sound file
└── README.md           # Quick reference
```

### Technology Stack

- **Pure HTML/CSS/JavaScript** - No frameworks or build tools
- **LocalStorage API** - Persistent data storage
- **Fetch API** - CoinGecko API integration
- **Web Audio API** - Alarm sound playback
- **setInterval** - Polling mechanism (15-second updates)

## Data Persistence: LocalStorage

All application state is stored in the browser's LocalStorage under a single key:

```javascript
localStorage.setItem('cryptoPairs', JSON.stringify(pairsData))
```

### Storage Schema

```json
{
  "BTCUSDT": {
    "currentPrice": 50000,
    "maxPrice": 52000,
    "minPrice": 48000,
    "priceHistory": [
      {"price": 50000, "timestamp": 1709000000000},
      {"price": 50100, "timestamp": 1709000015000}
    ],
    "alarms": [
      {
        "type": "target",
        "targetPrice": 55000,
        "direction": "fromBelow",
        "triggered": false
      },
      {
        "type": "percentChange",
        "percentage": 5,
        "changeType": "downFromMax",
        "triggered": false
      },
      {
        "type": "timeframe",
        "percentage": 3,
        "timeValue": 30,
        "timeUnit": "minutes",
        "direction": "any",
        "startPrice": 50000,
        "startTime": 1709000000000,
        "triggered": false
      }
    ]
  }
}
```

### LocalStorage Benefits

- **Zero Configuration**: Works immediately, no setup
- **Privacy**: Data never leaves the browser
- **Portability**: Copy HTML files to any device
- **Offline Access**: View historical data without internet

### LocalStorage Limitations

- **Storage Quota**: Typically 5-10MB per origin
- **Browser-Specific**: Data doesn't sync across browsers/devices
- **Clearing Risk**: Browser cache clear = data loss
- **Single-User**: No multi-user support

## Price Update Mechanism

### Polling Loop

```javascript
// 15-second polling interval
setInterval(async () => {
  for (const pair of activePairs) {
    const price = await fetchPriceFromCoinGecko(pair);
    updatePairData(pair, price);
    checkAlarms(pair);
  }
  saveToLocalStorage();
}, 15000);
```

### CoinGecko API Integration

The app uses CoinGecko's **free public API** (no authentication required):

**For Stablecoin Pairs** (quote = USDT/USDC/USD/BUSD/DAI):
```javascript
// Example: BTCUSDT
// Fetch BTC price in USD (stablecoins treated as $1)
fetch('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd')
```

**For Crypto Pairs** (quote = BTC/ETH/BNB):
```javascript
// Example: ETHBTC
// Fetch both ETH and BTC prices, calculate ratio
fetch('https://api.coingecko.com/api/v3/simple/price?ids=ethereum,bitcoin&vs_currencies=usd')
// price = ethPrice / btcPrice
```

### Price History Management

- **Retention**: 24 hours of price data
- **Granularity**: One data point per 15-second interval (5,760 points/day)
- **Cleanup**: Automatic removal of data older than 24 hours
- **Purpose**: Powers timeframe alarms (e.g., "5% in 2 hours")

```javascript
// Cleanup old price history
priceHistory = priceHistory.filter(
  point => Date.now() - point.timestamp < 24 * 60 * 60 * 1000
);
```

## Alarm Sound System

### Web Audio API Implementation

```javascript
const audio = new Audio('alarm.mp3');
audio.loop = true;  // Continuous playback
audio.volume = 0.6; // 60% volume

// Trigger alarm
function playAlarm() {
  audio.play().catch(err => {
    console.error('Audio playback failed:', err);
    // Fallback: Visual-only alarm
  });
}

// User dismisses alarm
function stopAlarm() {
  audio.pause();
  audio.currentTime = 0; // Reset to start
}
```

### Browser Audio Context Limitations

{{% notice warning "CRITICAL: Keep Tab Visible for Reliable Alarms" %}}
**Browser audio contexts are suspended for inactive tabs to save resources.**

For the most reliable alarm sound:
- ✅ **Keep the browser tab VISIBLE** or use a separate window
- ✅ Avoid minimizing or switching tabs for extended periods
- ✅ Browser audio can be suspended after 5-10 minutes of inactivity

**Why this happens**: Browsers like Chrome, Firefox, and Edge automatically suspend background audio contexts to reduce CPU usage and battery drain. This is a browser security/performance feature, not a bug.

**Backup**: Even if audio fails, the page title will flash "🚨 ALARM TRIGGERED! 🚨" as a visual indicator.
{{% /notice %}}

{{% notice info "Test Your Alarm Sound" %}}
**Before relying on alarms, verify audio works:**

1. Click the "🔔 Test Alarm" button in the UI
2. You should hear a continuous alarm sound
3. Ensure your system volume is adequate (alarm plays at 60%)
4. Check that your browser allows audio playback from the site

If you don't hear sound, check:
- Browser permissions (may need to click page first for autoplay)
- System volume and mute settings
- Browser console (F12) for audio errors
{{% /notice %}}

**Visual Fallback Implementation**:
```javascript
// Visual fallback when audio fails
document.title = '🚨 ALARM TRIGGERED! 🚨';
setInterval(() => {
  document.title = document.title === '🚨 ALARM TRIGGERED! 🚨'
    ? 'Crypto Price Alarm'
    : '🚨 ALARM TRIGGERED! 🚨';
}, 1000);
```

## User Interface

### HTML Structure

- **Minimal Dependencies**: No UI frameworks
- **Inline CSS**: All styles in `<style>` block
- **Responsive Design**: Mobile-friendly layout
- **Accessibility**: Semantic HTML, clear labels

### Key UI Components

1. **Pair Management Panel**
   - Add new pairs input
   - Active pairs list
   - Remove pair button
   - Alarm count badge

2. **Alarm Configuration Modal**
   - Three alarm type tabs
   - Dynamic form inputs
   - Alarm list display
   - Back to assets button

3. **Alarm Trigger Modal**
   - Alarm details
   - Dismiss button
   - Sound playing indicator

## Deployment

### Option 1: Local File System
```bash
cd javascript-app
open index.html  # macOS
start index.html # Windows
xdg-open index.html # Linux
```

### Option 2: Simple HTTP Server
```bash
cd javascript-app
python -m http.server 8000
# Access at http://localhost:8000
```

### Option 3: Static Hosting
Upload `javascript-app/` folder to:
- GitHub Pages
- Netlify
- Vercel
- Any static file host

## Advantages

1. **Zero Friction**: Double-click HTML file to run
2. **No Dependencies**: Works offline after first load
3. **Privacy**: Data stored locally only
4. **Portability**: Copy folder to any device
5. **Simplicity**: ~500 lines of readable code

## Limitations

1. **Single User**: No multi-user support
2. **Tab Must Stay Open**: Browser must remain running
3. **No Server-Side Logic**: Can't run headless
4. **Storage Quota**: LocalStorage size limits
5. **Browser Dependency**: Requires modern browser

## Use Cases

**Ideal For**:
- Personal crypto monitoring
- Quick setup without infrastructure
- Learning/education purposes
- Portable USB deployment
- Privacy-conscious users

**Not Ideal For**:
- Team/shared monitoring
- Server-side automation
- Headless operation
- Large-scale deployments

## Performance Considerations

### Memory Management
- Price history capped at 24 hours
- Automatic cleanup on each update
- Typical memory usage: < 10MB

### Network Usage
- API call every 15 seconds per pair
- ~2KB per API response
- Daily usage: ~11.5MB per pair

### Browser Compatibility
- Chrome/Edge: ✅ Full support
- Firefox: ✅ Full support
- Safari: ✅ Full support (audio may require interaction)
- Mobile browsers: ✅ Works but keep screen on

## Debugging

### Common Issues

**Alarms not triggering**:
```javascript
// Check in browser console
console.log('Current price:', pair.currentPrice);
console.log('Alarm conditions:', pair.alarms);
```

**LocalStorage data corruption**:
```javascript
// Clear and reset
localStorage.removeItem('cryptoPairs');
location.reload();
```

**Audio not playing**:
```javascript
// Check audio context state
console.log('Audio ready:', audio.readyState);
console.log('Audio error:', audio.error);
```

## Next Steps

- Explore **Alarm Logic** for detailed alarm type documentation
- See **API Integration** for CoinGecko implementation details
- Compare with **Python App** for server-side alternative
