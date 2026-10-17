---
title: "Browser UI"
weight: 2
---

# Browser UI

## Overview

The browser interface is plain ES modules plus the Socket.IO client, with no framework and no build step. It keeps no data of its own: everything it shows (prices, alarm descriptions, "% till trigger", stale flags) is computed on the server and arrives over Socket.IO. The browser renders it, plays the alarm sound and flashes the page title.

```
crypto_alarm/
├── templates/index.html
└── static/
    ├── css/styles.css
    ├── vendor/socket.io.min.js
    └── js/
        ├── main.js     # socket wiring, forms, navigation, status badge
        ├── views.js    # rendering of pairs, alarm table, per-pair alarm list
        ├── modal.js    # the alarm dialog, queue, flashing title
        ├── audio.js    # pulsing alarm tone (Web Audio API)
        └── dom.js      # tiny DOM helpers
```

{{% notice info "Server MIME type for JavaScript" %}}
`main.js` is loaded as an ES module, and browsers refuse modules that are not served as JavaScript. Windows can map `.js` to `text/plain` in the registry, so `web.py` registers `text/javascript` for `.js` at import time. Without that, the page stays on "Connecting..." forever.
{{% /notice %}}

## Screens

### Overview

- **Add trading pair**: enter a symbol such as `BTCUSDT`; errors (unknown symbol, already added) appear below the field
- **Monitored pairs** tab: one row per pair with the formatted price, the 24-hour change (green or red), the alarm count, a **stale** badge when the price is older than two minutes, and **Alarms** / **Remove** buttons
- **All active alarms** tab: a table of every armed alarm, grouped by pair, with its description and **% till trigger**

### Configure alarms

Opening **Alarms** for a pair shows:

- The pair's tracked **max and min** price, with a **Reset max/min** button
- Three forms: **Target price alert**, **% change from max/min** and **% move in timeframe**
- The pair's **active alarms**, flagged `TRIGGERED` or `RESETTING...` when relevant

Choosing **Since start** as the timeframe unit disables the time amount field.

### Status badge

The header badge reflects the browser's Socket.IO connection and the server's price feed:

| Badge | Meaning |
|-------|---------|
| Live | prices are streaming from Binance |
| Live (REST fallback) | the stream is down, prices come from REST polling |
| Connecting to Binance... | the feed has just started |
| Binance feed down | neither the stream nor REST is delivering prices |
| Connected | connected, with no pairs added yet |
| Disconnected | the browser lost its connection to the server |

### % till trigger

How many percentage points a price still has to move before the alarm fires, computed by the server. `N/A` means it can't be computed yet (for example a timeframe alarm without enough history).

## The Alarm Dialog

When an alarm triggers, the browser shows a modal dialog:

- A big **▲ UP** or **▼ DOWN** indicator and the alarm message
- A pulsing sawtooth tone at 880 Hz and 60% volume that plays until the alarm is dismissed
- A flashing page title (`🚨 ALARM TRIGGERED! 🚨` / `⚠️ PRICE ALARM ⚠️`), visible even from another tab
- **DISMISS ALARM** closes the dialog, stops the sound and tells the server the trigger was seen (`ack_alarm`)
- **RESTART (60s)** appears for target alarms: it dismisses and re-arms the alarm after the 60-second cooldown

If several alarms fire together they are queued and shown one after another; duplicates are ignored. The dialog traps keyboard focus, and **Escape** dismisses it.

### Sound and browser limits

Browsers only allow audio after a user gesture. The app unlocks audio on the first click anywhere on the page and when you press **Test alarm**.

{{% notice warning "Background tabs" %}}
Alarm *evaluation* happens on the server, so a hidden tab never causes a missed alarm. Only the sound and the title flash are browser-side, and browsers may throttle both in tabs that have been in the background for a long time.

For alarms that must reach you, configure a server-side channel (ntfy, Telegram or webhook) as described in [Python App]({{% relref "/implementations/python-app" %}}#notifications-when-no-browser-is-open). Triggers that nobody dismissed are also shown again, with sound, when a browser next connects.
{{% /notice %}}

{{% notice info "Test Your Alarm Sound" %}}
Use the **Test alarm** button in the header before relying on an alarm. It shows a test dialog and plays the real alarm tone so you can check your system volume.
{{% /notice %}}

## Rendering

- Updates arrive as a full-state `price_update` every two seconds
- Several events in the same frame are coalesced into a single render with `requestAnimationFrame`
- Lists are reconciled by key (`ticker` or alarm id), and text is only assigned when it changed, so hover, focus and in-flight clicks survive the frequent updates
- All text goes in as text nodes, never parsed as HTML

## Browser Compatibility

Requires a modern browser with ES modules, private class fields and the Web Audio API (current Chrome, Edge, Firefox and Safari). The page declares `color-scheme: light dark` and follows your system theme.

## Debugging

### Common Issues

**Stuck on "Connecting..."**
- Open the browser's developer console: a module MIME type error means `.js` is not served as JavaScript (see above)
- Check that the server is running and the page was opened from the same host and port it serves
- If you opened the page from a different origin, add it to `CRYPTO_ALARM_ALLOWED_ORIGINS`

**"Disconnected"**
- The server stopped or the network dropped; the browser reconnects automatically and receives the full state again

**No sound**
- Press **Test alarm**, and click the page once so the browser allows audio
- Check the system volume and the tab's mute state

**Prices show a "stale" badge**
- No price has arrived for two minutes; check the status badge and `/healthz`

## Next Steps

- See **Alarm Logic** for what each alarm type checks
- See **API Integration** for where the prices come from
