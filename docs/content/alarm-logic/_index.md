---
title: "Alarm Logic"
weight: 3
chapter: true
---

# Alarm Logic: Deep Dive

## Overview

The Crypto Price Alarm system implements three distinct alarm types, each designed for different trading strategies and monitoring needs. All alarms are evaluated by the server once a second against the live price from Binance, so they keep working with no browser open.

## The Three Alarm Types

### 1. Target Price Alert
**Use Case**: Notify when price crosses a specific value

**Configuration**:
- Target price (in quote currency)
- Direction: `any`, `up` (from below), `down` (from above)

**Examples**:
- BTCUSDT @ $55,000 from below (breakout alert)
- ETHBTC @ 0.055 from above (breakdown alert)
- SOLUSDC @ $100 any direction (proximity alert)

---

### 2. % from Max/Min
**Use Case**: Track percentage moves away from extremes

**Configuration**:
- Percentage threshold (e.g., 5%)
- Reference: `max` (price falls X% below the max) or `min` (price rises X% above the min)

**Examples**:
- Alert when BTC drops 10% from the highest price seen since the pair was added
- Alert when ETH rises 15% from the lowest price seen

---

### 3. % Move in Timeframe
**Use Case**: Detect significant price movement within a time window

**Configuration**:
- Percentage threshold (e.g., 3%)
- Direction: `any`, `up`, `down`
- Time value + unit: minutes, hours, days (up to 7 days), or "since start"

**Examples**:
- 5% move (any direction) in 15 minutes (volatility alert)
- 10% up in 2 hours (pump detector)
- 20% down in 3 days (crash alert)
- 8% move since start (session tracker - repeats and re-arms itself)

## Implementation Architecture

### Alarm Checking Flow

```
Price tick (Binance WebSocket, or REST fallback)
  ↓
Update pair data (price, 24h stats, max price, min price)
  ↓
Append to price history (at most one sample per 30 s, 8-day retention)

Once a second, for each alarm:
  ↓
  Target alarm cooldown over? → re-arm from the current price
  ↓
  Already triggered? → skip
  ↓
  Price older than 120 s? → skip
  ↓
  Run the type-specific check (rules.py)
  ↓
  Condition met? → mark triggered, save, then:
       - send ntfy / Telegram / webhook notifications
       - emit alarm_triggered to every connected browser
```

### Alarm State Machine

```
┌─────────────┐
│    ARMED    │ ← Initial state after creation
└─────┬───────┘
      │
      │ Price meets condition
      ↓
┌─────────────┐
│  TRIGGERED  │ ← acknowledged = false: replayed to browsers that connect
└─────┬───────┘
      │
      │ User dismisses (ack_alarm)
      ↓
┌─────────────┐
│ DISMISSED   │ ← acknowledged = true; stays TRIGGERED (inactive) until removed
└─────┬───────┘
      │
      │ Target alarms only: RESTART (60 s cooldown)
      ↓
┌─────────────┐
│ RESETTING   │ ← disarmed for 60 s, then back to ARMED from the current price
└─────────────┘

Exception: "Since start" timeframe alarms never become TRIGGERED. They restart their
start price at the current price and stay ARMED.
```

An alarm that triggered and was dismissed stays in the list flagged `TRIGGERED` and no longer fires. Remove it, or (target alarms only) restart it.

## Alarm Type 1: Target Price

### Logic Implementation

The server remembers the price from the previous evaluation (`prevPrice`) and fires when the price crosses the target **between two evaluations**:

```python
def check_target(alarm, price):
    target, prev, direction = alarm.target_price, alarm.prev_price, alarm.direction

    if prev is None:                       # first evaluation of a new alarm
        if direction == "up":
            return (True, "up") if price >= target else (False, None)
        if direction == "down":
            return (True, "down") if price <= target else (False, None)
        if abs(price - target) / target < 0.001:     # 'any': within 0.1%
            return True, "up" if price >= target else "down"
        return False, None

    if direction in ("up", "any") and prev < target <= price:
        return True, "up"
    if direction in ("down", "any") and prev > target >= price:
        return True, "down"
    return False, None
```

### Direction Modes Explained

**`up` (from below)**: fires when the price rises to or through the target
- Target $60,000: fires when the price goes from below $60,000 to $60,000 or more

**`down` (from above)**: fires when the price falls to or through the target
- Target $60,000: fires when the price goes from above $60,000 to $60,000 or less

**`any`**: fires on a crossing in either direction

### Visual Representation

```
Price
  ^
  |          ╱╲
60000 ──────╱──╲────────  ← Target (from below)
  |        ╱    ╲
  |   ╱╲  ╱      ╲
  |  ╱  ╲╱
  +──────────────────────> Time
         ↑
     fires once, on the tick that crosses
```

### Edge Cases

**The price is already past the target when you create the alarm**
- `up`: fires immediately if the price is at or above the target
- `down`: fires immediately if the price is at or below the target
- `any`: fires immediately only if the price is within 0.1% of the target; otherwise the alarm waits for a real crossing

A new alarm is therefore never silently dead.

**Price oscillates around the target**
- The alarm triggers once and then stays triggered, so oscillation cannot spam you
- After **RESTART**, the alarm re-arms from the *current* price, so only a *new* crossing fires. If the price is still above the target when the cooldown ends, nothing happens until it crosses again.

**Stale price**
- If the last price is older than two minutes the alarm is skipped and cannot fire on old data

## Alarm Type 2: % from Max/Min

### Logic Implementation

```python
def check_extreme(alarm, asset):
    if alarm.extreme_type == "max":
        peak = asset.max_price
        if peak > 0 and (peak - asset.price) / peak * 100 >= alarm.percentage:
            return True, "down"
    else:
        trough = asset.min_price
        if trough > 0 and (asset.price - trough) / trough * 100 >= alarm.percentage:
            return True, "up"
    return False, None
```

### Max/Min Tracking

Every price tick updates the pair's extremes:

```python
if price > asset.max_price: asset.max_price = price
if price < asset.min_price: asset.min_price = price
```

Both start at the price when you added the pair. They track **every tick seen since then** (or since the last **Reset max/min**), not the 24-hour high and low. The 24-hour high and low from Binance are only shown for information.

### Percentage Calculation Examples

**Down from max** (peak $65,000, price $58,500):
```
(65000 - 58500) / 65000 × 100 = 10.0%   → a "10% down from max" alarm fires
```

**Up from min** (trough $45,000, price $51,750):
```
(51750 - 45000) / 45000 × 100 = 15.0%   → a "15% up from min" alarm fires
```

### Use Cases by Strategy

- **Trailing stop**: "10% down from max" tells you when a rally has given back 10%
- **Dip buying**: "5% up from min" tells you when a bottom is bouncing
- **Profit protection**: after buying, reset max/min so the max starts at your entry

### Persistence Behavior

{{% notice info "Max/Min Prices Persist Across Restarts" %}}
**Important**: Max and min prices are saved in `data/crypto_data_binance.json` and survive server restarts. They are shared by all connected browsers.

**To reset max/min values**: open the pair's **Alarms** screen and press **Reset max/min**. Tracking restarts from the current price. Removing and re-adding the pair also works, but deletes the pair's alarms.

**Example**: If you added BTCUSDT when BTC was $45,000, and it later reached $65,000 (new max), that $65,000 max persists even after a restart. Your "10% down from max" alarm will still use $65,000 as the reference.

New highs and lows are written to disk at most every 30 seconds.
{{% /notice %}}

{{% notice warning "Resetting does not re-arm" %}}
**Reset max/min** only changes the reference prices. An extreme alarm that already triggered stays triggered; remove it and create a new one to arm it again.
{{% /notice %}}

## Alarm Type 3: % Move in Timeframe

### Logic Implementation

```python
def check_timeframe(alarm, price, history, now):
    if alarm.time_unit == "since_start":
        start = alarm.start_price
    else:
        start = price_at(history, now - window_seconds(alarm))   # price one full window ago

    if not start:
        return False, None, start          # not enough history yet

    change = (price - start) / start * 100
    if alarm.direction in ("up", "any") and change >= alarm.percentage:
        return True, "up", start
    if alarm.direction in ("down", "any") and change <= -alarm.percentage:
        return True, "down", start
    return False, None, start
```

The windowed alarm compares the current price with **the price exactly one window ago**: `price_at` returns the latest history sample at or before `now - window`. It is a point-to-point comparison, not a high-to-low range within the window.

### Time Unit Conversion

```python
TIME_UNITS = {"minutes": 60, "hours": 3600, "days": 86400}
MAX_WINDOW_SECONDS = 7 * 86400
```

The time amount must be a whole number of at least 1, and the whole window cannot exceed **7 days**.

### Timeframe Types

#### Fixed Timeframes (minutes, hours, days)

- Compared against the price one full window ago, re-evaluated every second
- The "start price" shown for "% till trigger" is the window-ago price and moves along with time
- Triggers **once**, then stays triggered until removed

**Example**: "5% up in 30 minutes" fires when `price now` is at least 5% above `price 30 minutes ago`.

#### "Since Start" Timeframe

- The reference is the price when the alarm was created (`startPrice`)
- When it triggers, it **does not** become inactive: the start price resets to the current price and the alarm watches for the next move
- Every trigger still shows the dialog and sends notifications; repeat notifications for the same alarm within 30 seconds are suppressed
- Because it never enters the "triggered, unacknowledged" state, a "since start" trigger is not replayed to browsers that connect later

### Direction Modes

- **`up`**: fires when the change is ≥ +percentage
- **`down`**: fires when the change is ≤ −percentage
- **`any`**: fires on either

### Price History Requirements

{{% notice warning "History Must Reach Back a Full Window" %}}
A fixed-timeframe alarm stays silent until price history goes back at least one full window. History is **not** built only from the time the app runs: when a pair is added, and again for every saved pair when the server starts, the server downloads candles from Binance:

- hourly closes for the last 8 days
- 5-minute closes for the last 24 hours

Live samples (at most one per 30 seconds) are added on top and kept for 8 days. A 7-day alarm therefore works immediately after adding a pair.

**Resolution**: for windows reaching further back than 24 hours, the reference price is the latest hourly close at or before the window start, so it can be up to an hour older than the exact window start.

**If the backfill fails** (Binance unreachable or rate-limited), a warning is logged and timeframe alarms on that pair wait until live samples cover the window. The history is held in memory only.
{{% /notice %}}

### Examples with Calculations

**Example 1: 5% up in 30 minutes**
```
Price 30 minutes ago: 50,000
Price now:            52,600
Change: (52600 - 50000) / 50000 × 100 = +5.2%  → fires (up)
```

**Example 2: 10% down in 2 hours**
```
Price 2 hours ago: 3,000
Price now:         2,680
Change: (2680 - 3000) / 3000 × 100 = -10.67%  → fires (down)
```

**Example 3: 8% any direction, since start**
```
Start price: 100.00
Price now:   92.00   → -8.0%  → fires (down)
New start price: 92.00; the alarm keeps watching
```

## Cross-Alarm Coordination

### Multiple Alarms on Same Pair

Alarms are independent: every alarm of a pair is evaluated on every pass. Several alarms can trigger on the same tick; each produces its own dialog (queued one after another in the browser) and its own notification.

### Alarm Priority

There is none. Alarms are evaluated in the order they were created, and each one decides for itself.

### Triggered State Management

- `triggered`: the alarm fired and is inactive
- `acknowledged`: `false` until a browser dismisses the trigger, then `true`
- Removing a pair removes all of its alarms
- While a target alarm is `RESETTING`, the Remove button on the pair's alarm list is disabled; the alarm re-arms by itself after the cooldown

## Performance Optimizations

### Efficient Alarm Checking

- The loop runs once a second regardless of how many ticks arrive, so checks never pile up
- Window lookups use binary search (`bisect`) over a time-sorted history list
- All checks happen under one lock and take microseconds; disk writes and notifications happen outside it
- Alarms are skipped entirely when their price is stale

### Price History Pruning

```python
if not samples or now - samples[-1][0] >= 30:     # history_spacing
    samples.append((now, price))
    drop samples older than now - 8 days          # history_retention
```

### Memory Considerations

At one sample per 30 seconds for 8 days a pair holds about 23,000 samples at most (fewer right after startup, because the backfill uses coarser hourly and 5-minute candles). History is not saved to disk.

## Testing Strategies

### Unit Testing Alarm Logic

The trigger rules are pure functions in `rules.py`, so they are tested with plain values and no clocks, threads or network:

```python
def test_crossing_up_and_down(self):
    self.assertEqual(rules.check_target(self.alarm("up", 99), 100), (True, "up"))
    self.assertEqual(rules.check_target(self.alarm("down", 101), 100), (True, "down"))

def test_silent_until_history_reaches_back_a_full_window(self):
    ...
```

Run them with:

```
python -m unittest discover -s tests
```

### Integration Testing

`tests/test_monitor.py` drives a real `Monitor` with a fake Binance client and an injected clock (`check_alarms(now)`), covering:

- adding a pair through `exchangeInfo`, and rejecting bad input
- a target alarm firing once on a crossing
- the restart cooldown not re-firing until a new crossing
- restart being limited to target alarms
- stale prices not triggering
- "since start" alarms repeating
- max/min tracking and reset
- history sampling and save/load round trips
- a corrupt data file being preserved
- removing a pair removing its alarms

### Manual Testing Scenarios

1. Add a pair and a target alarm slightly above the current price, then wait for the dialog
2. Press **Test alarm** to check sound and volume
3. Create an alarm, close every browser tab, and confirm a notification arrives (with a channel configured)
4. Stop the server (Ctrl+C), restart it, and confirm pairs, alarms and max/min are still there

## Common Pitfalls & Solutions

### Pitfall 1: The Alarm Never Fires Again

**Symptom**: An alarm fired once and nothing happens now.

**Cause**: Fixed alarms trigger once and then stay triggered.

**Solution**: Use **RESTART** on target alarms, create a new alarm for other types, or use a "since start" timeframe alarm if you want repeats.

### Pitfall 2: A Timeframe Alarm Stays Silent

**Cause**: History does not reach back a full window (backfill failed, or the pair is brand new and Binance has no older candles).

**Solution**: Check the logs for "History backfill ... failed", restart the server to retry, or use a shorter window.

### Pitfall 3: Alarms Seem Frozen

**Cause**: The pair shows a **stale** badge: no price for two minutes, and stale prices are ignored on purpose.

**Solution**: Check the header status badge and `/healthz`; see the [Binance Integration]({{% relref "/api-integration/binance" %}}) troubleshooting section.

### Pitfall 4: Percent Alarms Use an Old Max

**Cause**: Max/min are tracked since the pair was added and are persisted.

**Solution**: Press **Reset max/min** to restart from the current price.

### Pitfall 5: Floating-Point Precision

Alarms compare floats directly, which is fine for prices, but the `any`-direction check on a brand new alarm uses a 0.1% tolerance rather than exact equality. For a target to fire exactly, rely on crossing detection rather than expecting the price to land exactly on the target.

## Practical Alarm Examples

### Real-World Trading Strategies

{{% notice tip "Starting Points" %}}
These are examples of how the three alarm types combine. Adjust thresholds based on your risk tolerance and market conditions.
{{% /notice %}}

#### For BTCUSDT (Stablecoin Pair)

{{< tabs >}}
{{% tab title="Bull Run Alerts" %}}

**Breakout Detection**:
- **Type**: Target Price
- **Target**: $60,000
- **Direction**: From below
- **Use Case**: Alert when Bitcoin breaks through resistance

**Momentum Confirmation**:
- **Type**: % Move in Timeframe
- **Percentage**: 3%
- **Direction**: Upward
- **Timeframe**: 30 minutes
- **Use Case**: Catch strong upward moves early

{{% /tab %}}

{{% tab title="Risk Management" %}}

**Stop Loss Protection**:
- **Type**: % from Max/Min
- **Percentage**: 10%
- **Reference**: % down from max
- **Use Case**: Protect profits when price drops from peak (press Reset max/min after you buy)

**Crash Detection**:
- **Type**: % Move in Timeframe
- **Percentage**: 15%
- **Direction**: Downward
- **Timeframe**: 1 day
- **Use Case**: Alert on significant daily drops

{{% /tab %}}

{{% tab title="Volatility Monitoring" %}}

**Short-term Volatility**:
- **Type**: % Move in Timeframe
- **Percentage**: 5%
- **Direction**: Any direction
- **Timeframe**: 15 minutes
- **Use Case**: Warn about fast moves in either direction

**Session Tracker**:
- **Type**: % Move in Timeframe
- **Percentage**: 3%
- **Direction**: Any direction
- **Timeframe**: Since start
- **Use Case**: A repeating alarm that fires on every further 3% move

{{% /tab %}}
{{< /tabs >}}

#### For ETHBTC (Crypto-to-Crypto Pair)

{{< tabs >}}
{{% tab title="Ratio Trading" %}}

**Outperformance Alert**:
- **Type**: Target Price
- **Target**: 0.055
- **Direction**: From below
- **Use Case**: Alert when ETH outperforms BTC past a ratio

{{% /tab %}}

{{% tab title="Reversal Detection" %}}

**Bounce Alert**:
- **Type**: % from Max/Min
- **Percentage**: 5%
- **Reference**: % up from min
- **Use Case**: Alert when the ratio recovers from its low

**Pullback Alert**:
- **Type**: % from Max/Min
- **Percentage**: 5%
- **Reference**: % down from max
- **Use Case**: Alert when the ratio retreats from its high

{{% /tab %}}

{{% tab title="Short-term Trading" %}}

**Intraday Move**:
- **Type**: % Move in Timeframe
- **Percentage**: 2%
- **Direction**: Any direction
- **Timeframe**: 2 hours
- **Use Case**: Catch significant intraday ratio moves

{{% /tab %}}
{{< /tabs >}}

### Multi-Alarm Strategy Example

**Conservative BTC Monitoring Setup** (3 alarms):

1. **Target Price**: $55,000 from below
   - Purpose: Breakout confirmation

2. **% from Max**: 10% down
   - Purpose: Stop-loss trigger

3. **% Move in Timeframe**: 5% in 30 minutes (any direction)
   - Purpose: High volatility warning

**Rationale**: This combination covers breakouts (bullish), risk management (bearish), and volatility detection (neutral).

### Tips for Setting Effective Alarms

{{% notice info "Alarm Best Practices" %}}

1. **Don't over-alarm**: Too many alarms means alarm fatigue. Start with 2-3 per pair.

2. **Account for volatility**:
   - High volatility assets (small caps): use wider thresholds (5-10%)
   - Low volatility assets (BTC/ETH): narrower thresholds work (2-5%)

3. **Timeframe selection**:
   - Day trading: 15-minute to 2-hour timeframes
   - Swing trading: 4-hour to 1-day timeframes
   - Long-term: use % from max/min instead of timeframes

4. **Test before relying**: Use the "Test alarm" button to verify audio works, and configure a notification channel for alarms that matter

5. **Direction matters**:
   - Use "from below" for breakouts
   - Use "from above" for breakdowns
   - Use "any" for proximity alerts

6. **"Since start" alarms**: great for continuous monitoring, but expect frequent triggers in volatile markets

{{% /notice %}}

## Next Steps

- Explore **API Integration** for how prices and history are fetched
- See **Implementations** for how the monitor loop and persistence work
- Check **DevOps** for testing and deployment
