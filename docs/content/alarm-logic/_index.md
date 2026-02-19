---
title: "Alarm Logic"
weight: 3
chapter: true
---

# Alarm Logic: Deep Dive

## Overview

The Crypto Price Alarm system implements three distinct alarm types, each designed for different trading strategies and monitoring needs. All alarms operate on the same core principle: continuous polling with condition checking.

## The Three Alarm Types

### 1. Target Price Alert
**Use Case**: Notify when price reaches a specific value

**Configuration**:
- Target price (in quote currency)
- Direction: `any`, `fromBelow`, `fromAbove`

**Examples**:
- BTCUSDT @ $55,000 from below (breakout alert)
- ETHBTC @ 0.055 from above (breakdown alert)
- SOLUSDC @ $100 any direction (proximity alert)

---

### 2. % Change from Max/Min
**Use Case**: Track percentage moves from extremes

**Configuration**:
- Percentage threshold (e.g., 5%)
- Change type: `downFromMax` or `upFromMin`

**Examples**:
- Alert when BTC drops 10% from its recorded high
- Alert when ETH rises 15% from its recorded low

---

### 3. % Move in Timeframe
**Use Case**: Detect significant price movement within a time window

**Configuration**:
- Percentage threshold (e.g., 3%)
- Direction: `any`, `up`, `down`
- Time value + unit: minutes, hours, days, or "since start"

**Examples**:
- 5% move (any direction) in 15 minutes (volatility alert)
- 10% up in 2 hours (pump detector)
- 20% down in 3 days (crash alert)
- 8% move since start (session tracker - auto-resets)

## Implementation Architecture

### Alarm Checking Flow

```
Price Update (every 15 seconds)
  ↓
Update pair data (currentPrice, maxPrice, minPrice)
  ↓
Update price history (24-hour rolling window)
  ↓
For each alarm:
  ↓
  Check alarm type → Execute specific logic
  ↓
  Condition met? → Trigger alarm
  ↓
  Mark as triggered (prevent re-trigger)
  ↓
Play alarm sound + Show modal
```

### Alarm State Machine

```
┌─────────────┐
│   ACTIVE    │ ← Initial state after creation
└─────┬───────┘
      │
      │ Price meets condition
      ↓
┌─────────────┐
│  TRIGGERED  │ ← Alarm fires, sound plays
└─────┬───────┘
      │
      │ User dismisses
      ↓
┌─────────────┐
│  DISMISSED  │ ← Alarm stays inactive
└─────────────┘

Exception: "Since start" timeframe alarms reset to ACTIVE after trigger
```

## Alarm Type 1: Target Price

### Logic Implementation

```javascript
function checkTargetPriceAlarm(alarm, currentPrice, previousPrice) {
  const { targetPrice, direction, triggered } = alarm;

  // Skip if already triggered
  if (triggered) return false;

  switch (direction) {
    case 'any':
      // Trigger when price crosses target in any direction
      return (previousPrice < targetPrice && currentPrice >= targetPrice) ||
             (previousPrice > targetPrice && currentPrice <= targetPrice);

    case 'fromBelow':
      // Trigger only when price crosses target going up
      return previousPrice < targetPrice && currentPrice >= targetPrice;

    case 'fromAbove':
      // Trigger only when price crosses target going down
      return previousPrice > targetPrice && currentPrice <= targetPrice;
  }
}
```

### Direction Modes Explained

**`any` direction**:
- Triggers when price reaches target from either direction
- Use for: Price proximity alerts

**`fromBelow` direction**:
- Triggers only when price crosses target going upward
- Use for: Breakout alerts, resistance breaks
- Example: Alert me when BTC breaks $60k resistance

**`fromAbove` direction**:
- Triggers only when price crosses target going downward
- Use for: Breakdown alerts, support breaks
- Example: Alert me if BTC falls below $50k support

### Visual Representation

```
Price action: $48k → $52k → $56k

Target: $50k, direction: fromBelow
  ✅ Triggers when price crosses $50k going up

Target: $50k, direction: fromAbove
  ❌ Does NOT trigger (price came from below)

Target: $50k, direction: any
  ✅ Triggers when price crosses $50k
```

### Edge Cases

**Rapid price oscillation**:
```javascript
// Price bounces: $49k → $51k → $49k → $51k
// Without triggered flag: Alarm fires multiple times
// With triggered flag: Fires once, then stays silent

if (!alarm.triggered && conditionMet) {
  alarm.triggered = true;
  triggerAlarm();
}
```

**Gap in price data**:
```javascript
// Previous: $48k, Current: $52k (target: $50k)
// crossingDetection still works due to >= comparison

if (previousPrice < targetPrice && currentPrice >= targetPrice) {
  // Catches the crossing even if exact price wasn't observed
}
```

## Alarm Type 2: % Change from Max/Min

### Logic Implementation

```javascript
function checkPercentChangeAlarm(alarm, currentPrice, maxPrice, minPrice) {
  const { percentage, changeType, triggered } = alarm;

  if (triggered) return false;

  if (changeType === 'downFromMax') {
    // Calculate percentage drop from recorded maximum
    const dropPercent = ((maxPrice - currentPrice) / maxPrice) * 100;
    return dropPercent >= percentage;
  }

  if (changeType === 'upFromMin') {
    // Calculate percentage rise from recorded minimum
    const risePercent = ((currentPrice - minPrice) / minPrice) * 100;
    return risePercent >= percentage;
  }
}
```

### Max/Min Tracking

**Initialization**:
```javascript
// When pair is added
pair.maxPrice = currentPrice;
pair.minPrice = currentPrice;
```

**Update on every price fetch**:
```javascript
if (currentPrice > pair.maxPrice) {
  pair.maxPrice = currentPrice;
}

if (currentPrice < pair.minPrice) {
  pair.minPrice = currentPrice;
}
```

### Percentage Calculation Examples

**Down from Max**:
```
Max price: $60,000
Current: $54,000
Threshold: 10%

Calculation: (60000 - 54000) / 60000 = 0.10 = 10%
✅ Alarm triggers
```

**Up from Min**:
```
Min price: $40,000
Current: $46,000
Threshold: 15%

Calculation: (46000 - 40000) / 40000 = 0.15 = 15%
✅ Alarm triggers
```

### Use Cases by Strategy

**Profit Protection (downFromMax)**:
- Set 5% drop alarm to lock in gains
- Monitor pullbacks from local highs
- Stop-loss alternative

**Bounce Detection (upFromMin)**:
- Alert on recovery from local lows
- Identify potential reversal points
- Buy opportunity notification

### Persistence Behavior

{{% notice info "Max/Min Prices Persist Across Restarts" %}}
**Important**: Max and min prices are saved and persist across browser/app restarts.

**JavaScript App**:
- Stored in browser's LocalStorage
- Survives page refresh and browser restart
- Tied to your browser (doesn't sync across devices)

**Python App**:
- Stored in `data/crypto_data_binance.json` on server
- Survives server restarts
- Shared across all connected clients

**To reset max/min values**: Remove the trading pair and re-add it. The max/min will restart from the current price.

**Example**: If you added BTCUSDT when BTC was $45,000, and it later reached $65,000 (new max), that $65,000 max persists even if you close and reopen the app. Your "10% down from max" alarm will still use $65,000 as the reference.
{{% /notice %}}

**Resetting max/min**:
```
Only way to reset: Remove pair and re-add it
New max/min starts from current price
```

## Alarm Type 3: % Move in Timeframe

### Logic Implementation

```javascript
function checkTimeframeAlarm(alarm, currentPrice, priceHistory) {
  const { percentage, timeValue, timeUnit, direction, startPrice, startTime, triggered } = alarm;

  if (triggered) return false;

  // Determine comparison price based on timeframe
  let comparePrice;
  let compareTime;

  if (timeUnit === 'sinceStart') {
    // Use alarm creation price
    comparePrice = startPrice;
    compareTime = startTime;
  } else {
    // Calculate milliseconds for timeframe
    const timeframeMs = getMilliseconds(timeValue, timeUnit);
    const cutoffTime = Date.now() - timeframeMs;

    // Find oldest price within timeframe
    const relevantHistory = priceHistory.filter(
      point => point.timestamp >= cutoffTime
    );

    if (relevantHistory.length === 0) {
      // Not enough history yet
      return false;
    }

    comparePrice = relevantHistory[0].price;
    compareTime = relevantHistory[0].timestamp;
  }

  // Calculate percentage change
  const changePercent = Math.abs((currentPrice - comparePrice) / comparePrice * 100);

  // Check direction
  switch (direction) {
    case 'any':
      return changePercent >= percentage;

    case 'up':
      return (currentPrice > comparePrice) && (changePercent >= percentage);

    case 'down':
      return (currentPrice < comparePrice) && (changePercent >= percentage);
  }
}
```

### Time Unit Conversion

```javascript
function getMilliseconds(value, unit) {
  const conversions = {
    'minutes': value * 60 * 1000,
    'hours': value * 60 * 60 * 1000,
    'days': value * 24 * 60 * 60 * 1000
  };
  return conversions[unit];
}
```

### Timeframe Types

#### Fixed Timeframes (minutes, hours, days)

**15-minute window**:
```
Current time: 10:30
Lookback to: 10:15
Compare current price to price at 10:15
```

**2-hour window**:
```
Current time: 14:00
Lookback to: 12:00
Compare current price to price at 12:00
```

#### "Since Start" Timeframe

**Special behavior**:
- Compares to price when alarm was created
- **Auto-resets after triggering** (unique to this alarm type)
- Continuous monitoring for recurring moves

**Lifecycle**:
```
1. Alarm created at $50,000 (startPrice = 50000)
2. Price moves to $54,000 (8% up)
3. Alarm triggers
4. User dismisses
5. Alarm RESETS: startPrice = 54000 (current price)
6. Monitoring continues for next 8% move
```

### Direction Modes

**`any` direction**:
```javascript
// Absolute value - triggers on ±5%
Math.abs(changePercent) >= threshold
```

**`up` direction**:
```javascript
// Only positive moves
(currentPrice > comparePrice) && (changePercent >= threshold)
```

**`down` direction**:
```javascript
// Only negative moves
(currentPrice < comparePrice) && (changePercent >= threshold)
```

### Price History Requirements

{{% notice warning "24-Hour Price History Requirement" %}}
**Timeframe alarms require historical price data to function.**

**How it works**:
- Price data collected every 15 seconds (one data point per update)
- Maximum retention: 24 hours (5,760 data points total)
- Older data automatically purged to save memory

**Important implications**:

1. **Fresh start**: When you first add a pair, there's no history yet
   - A "2-hour timeframe" alarm won't work until 2 hours of data collected
   - A "1-day timeframe" alarm won't work until 24 hours have passed

2. **Insufficient history**: If you try to set a 4-hour alarm but only have 1 hour of history, the alarm will remain silent until enough data accumulates

3. **App/browser restart**:
   - JavaScript app: History persists in LocalStorage
   - Python app: History persists in JSON file
   - Both: History survives restarts, no need to wait again

4. **"Since start" alarms**: These work immediately (they use the alarm creation time as the reference, not historical data)

**Recommendation**: For best results, let the app run for a few hours before setting long timeframe alarms.
{{% /notice %}}

**Storage efficiency**:
```javascript
// Cleanup old data (runs on every price update)
priceHistory = priceHistory.filter(
  point => Date.now() - point.timestamp < 24 * 60 * 60 * 1000
);
```

**Insufficient history handling**:
```javascript
if (relevantHistory.length === 0) {
  // Not enough data yet for this timeframe
  // Alarm stays silent until sufficient history accumulated
  return false;
}
```

### Examples with Calculations

**Example 1: 5% in 30 minutes**

```
Time: 10:30
Lookback: 10:00

Price at 10:00: $50,000
Price at 10:30: $52,500

Change: (52500 - 50000) / 50000 = 0.05 = 5%
Direction: up
✅ Alarm triggers
```

**Example 2: 10% any direction in 2 hours**

```
Time: 14:00
Lookback: 12:00

Price at 12:00: $55,000
Price at 14:00: $49,000

Change: |49000 - 55000| / 55000 = 0.109 = 10.9%
Direction: any (absolute value)
✅ Alarm triggers
```

**Example 3: 3% down in 1 day**

```
Time: 10:00 (Day 2)
Lookback: 10:00 (Day 1)

Price at Day 1: $60,000
Price at Day 2: $57,000

Change: (60000 - 57000) / 60000 = 0.05 = 5%
Direction: down
✅ Alarm triggers (exceeds 3% threshold)
```

## Cross-Alarm Coordination

### Multiple Alarms on Same Pair

Alarms are **independent** - each checks conditions separately:

```javascript
// Example: BTCUSDT with 3 alarms
alarms = [
  { type: 'target', targetPrice: 55000 },
  { type: 'percentChange', percentage: 10, changeType: 'downFromMax' },
  { type: 'timeframe', percentage: 5, timeValue: 30, timeUnit: 'minutes' }
];

// All three can trigger in the same update cycle
for (const alarm of alarms) {
  if (checkAlarm(alarm)) {
    triggerAlarm(alarm);
  }
}
```

### Alarm Priority

**No priority system** - all alarms have equal weight:
- Multiple alarms can trigger simultaneously
- Modal shows first triggered alarm
- User dismisses one by one

### Triggered State Management

```javascript
// Once triggered, alarm stays inactive
alarm.triggered = true;

// User must manually remove and re-add to reuse
// (Except "since start" timeframe alarms - auto-reset)
```

## Performance Optimizations

### Efficient Alarm Checking

```javascript
// Skip triggered alarms early
function checkAlarms(pair) {
  for (const alarm of pair.alarms) {
    if (alarm.triggered) continue; // Skip immediately

    const triggered = checkAlarmCondition(alarm, pair);
    if (triggered) {
      handleAlarmTrigger(alarm, pair);
    }
  }
}
```

### Price History Pruning

```javascript
// Only keep relevant history
function pruneHistory(priceHistory) {
  const cutoff = Date.now() - (24 * 60 * 60 * 1000);
  return priceHistory.filter(point => point.timestamp >= cutoff);
}
```

### Memory Considerations

**Per pair**:
- Current price: 8 bytes
- Max/min prices: 16 bytes
- Price history (24h): ~46KB (5760 points × 8 bytes)
- Alarms: ~200 bytes each

**For 10 pairs with 5 alarms each**:
- Total memory: ~500KB

## Testing Strategies

### Unit Testing Alarm Logic

```javascript
// Test target price - from below
test('target price alarm - fromBelow', () => {
  const alarm = {
    type: 'target',
    targetPrice: 50000,
    direction: 'fromBelow',
    triggered: false
  };

  const result = checkTargetPriceAlarm(alarm, 50100, 49900);
  expect(result).toBe(true);
});

// Test percent change - down from max
test('percent change - downFromMax', () => {
  const alarm = {
    type: 'percentChange',
    percentage: 10,
    changeType: 'downFromMax',
    triggered: false
  };

  const result = checkPercentChangeAlarm(alarm, 54000, 60000, 40000);
  expect(result).toBe(true);
});
```

### Integration Testing

```javascript
// Test full alarm lifecycle
test('alarm triggers and marks as triggered', () => {
  const pair = createPair('BTCUSDT');
  const alarm = addTargetAlarm(pair, 55000, 'fromBelow');

  // Simulate price update
  updatePrice(pair, 55100);

  expect(alarm.triggered).toBe(true);
  expect(alarmModal.isVisible()).toBe(true);
});
```

### Manual Testing Scenarios

1. **Rapid triggering test**: Set very low thresholds and verify single trigger
2. **Direction test**: Verify `fromBelow` doesn't trigger when price comes from above
3. **History test**: Create timeframe alarm, wait for sufficient data
4. **Reset test**: Verify "since start" alarms reset after trigger

## Common Pitfalls & Solutions

### Pitfall 1: Alarm Triggers Multiple Times

**Problem**: Alarm fires on every price check
```javascript
// ❌ Bad: No triggered flag
if (currentPrice >= targetPrice) {
  triggerAlarm();
}
```

**Solution**: Use triggered flag
```javascript
// ✅ Good: Check triggered state
if (!alarm.triggered && currentPrice >= targetPrice) {
  alarm.triggered = true;
  triggerAlarm();
}
```

### Pitfall 2: Insufficient Price History

**Problem**: Timeframe alarm fails silently
```javascript
// ❌ Bad: Assumes history exists
const oldPrice = priceHistory[0].price;
```

**Solution**: Validate history length
```javascript
// ✅ Good: Check history availability
if (priceHistory.length === 0) return false;
```

### Pitfall 3: Floating-Point Precision

**Problem**: Percentage calculations drift
```javascript
// ❌ Bad: Direct float comparison
if (changePercent === 5.0) // May never match exactly
```

**Solution**: Use threshold comparison
```javascript
// ✅ Good: >= comparison
if (changePercent >= 5.0)
```

## Practical Alarm Examples

### Real-World Trading Strategies

{{% notice tip "Copy These Proven Alarm Configurations" %}}
These examples are based on actual trading strategies. Adjust thresholds based on your risk tolerance and market conditions.
{{% /notice %}}

#### For BTCUSDT (Stablecoin Pair)

{{< tabs >}}
{{% tab title="Bull Run Alerts" %}}

**Breakout Detection**:
- **Type**: Target Price
- **Target**: $60,000
- **Direction**: From Below
- **Use Case**: Alert when Bitcoin breaks through resistance

**Momentum Confirmation**:
- **Type**: % Move in Timeframe
- **Percentage**: 3%
- **Direction**: Up
- **Timeframe**: 30 minutes
- **Use Case**: Catch strong upward moves early

{{% /tab %}}

{{% tab title="Risk Management" %}}

**Stop Loss Protection**:
- **Type**: % Change from Max/Min
- **Percentage**: 10%
- **Change Type**: Down from Max
- **Use Case**: Protect profits when price drops from peak

**Crash Detection**:
- **Type**: % Move in Timeframe
- **Percentage**: 15%
- **Direction**: Down
- **Timeframe**: 1 day
- **Use Case**: Alert on significant daily drops

{{% /tab %}}

{{% tab title="Volatility Monitoring" %}}

**Short-term Volatility**:
- **Type**: % Move in Timeframe
- **Percentage**: 5%
- **Direction**: Any
- **Timeframe**: 2 hours
- **Use Case**: Detect unusual price action

**Session Tracker**:
- **Type**: % Move in Timeframe
- **Percentage**: 8%
- **Direction**: Any
- **Timeframe**: Since Start
- **Use Case**: Get alerted on every 8% move (auto-resets)

{{% /tab %}}
{{< /tabs >}}

#### For ETHBTC (Crypto-to-Crypto Pair)

{{< tabs >}}
{{% tab title="Ratio Trading" %}}

**Breaking Resistance**:
- **Type**: Target Price
- **Target**: 0.06
- **Direction**: From Below
- **Use Case**: ETH gaining strength vs BTC

**Support Level**:
- **Type**: Target Price
- **Target**: 0.05
- **Direction**: From Above
- **Use Case**: ETH weakening vs BTC

{{% /tab %}}

{{% tab title="Reversal Detection" %}}

**Ratio Recovery**:
- **Type**: % Change from Max/Min
- **Percentage**: 5%
- **Change Type**: Up from Min
- **Use Case**: ETH bottoming out vs BTC

**Ratio Weakness**:
- **Type**: % Change from Max/Min
- **Percentage**: 5%
- **Change Type**: Down from Max
- **Use Case**: ETH losing ground vs BTC

{{% /tab %}}

{{% tab title="Short-term Trading" %}}

**Quick Ratio Spike**:
- **Type**: % Move in Timeframe
- **Percentage**: 2%
- **Direction**: Any
- **Timeframe**: 15 minutes
- **Use Case**: Catch rapid ratio changes

**Trending Move**:
- **Type**: % Move in Timeframe
- **Percentage**: 10%
- **Direction**: Up
- **Timeframe**: 4 hours
- **Use Case**: Identify ETH outperformance trends

**Swing Trading**:
- **Type**: % Move in Timeframe
- **Percentage**: 5%
- **Direction**: Any
- **Timeframe**: Since Start
- **Use Case**: Continuous swing alerts (resets on trigger)

{{% /tab %}}
{{< /tabs >}}

### Multi-Alarm Strategy Example

**Conservative BTC Monitoring Setup** (3 alarms):

1. **Target Price**: $55,000 from below
   - Purpose: Breakout confirmation

2. **% Change from Max**: 10% down
   - Purpose: Stop-loss trigger

3. **% Move in Timeframe**: 5% in 30 minutes (any direction)
   - Purpose: High volatility warning

**Rationale**: This combination covers breakouts (bullish), risk management (bearish), and volatility detection (neutral).

### Tips for Setting Effective Alarms

{{% notice info "Alarm Best Practices" %}}

1. **Don't over-alarm**: Too many alarms = alarm fatigue. Start with 2-3 per pair.

2. **Account for volatility**:
   - High volatility assets (small caps): Use wider thresholds (5-10%)
   - Low volatility assets (BTC/ETH): Narrower thresholds work (2-5%)

3. **Timeframe selection**:
   - Day trading: 15-minute to 2-hour timeframes
   - Swing trading: 4-hour to 1-day timeframes
   - Long-term: Use % from max/min instead of timeframes

4. **Test before relying**: Use the "Test Alarm" button to verify audio works

5. **Direction matters**:
   - Use "from below" for breakouts
   - Use "from above" for breakdowns
   - Use "any" for proximity alerts

6. **"Since start" alarms**: Great for continuous monitoring, but expect frequent triggers in volatile markets

{{% /notice %}}

## Next Steps

- Explore **API Integration** for price fetching details
- See **Implementations** for language-specific alarm code
- Check **DevOps** for testing and deployment strategies
