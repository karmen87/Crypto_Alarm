# Crypto Price Alarm

A reliable web application for tracking cryptocurrency trading pairs and receiving alarm notifications when specific price events occur.

## Project Structure

This repository contains two separate implementations of the Crypto Price Alarm:

- **`javascript-app/`** - Standalone JavaScript application (client-side only, no server required)
- **`python-app/`** - Flask-based Python application (server-side with WebSocket support)

Both applications provide the same core functionality but use different technologies. Choose the one that best fits your needs.

## Features

- **Trading Pair Support**: Monitor any trading pair available on CoinGecko (BTCUSDT, ETHBTC, etc.)
- **Multi-Pair Tracking**: Monitor multiple trading pairs simultaneously
- **Real-Time Price Updates**: Prices update every 15 seconds using CoinGecko API
- **Three Alarm Types**:
  1. **Target Price**: Alert when price reaches a specific value (from above, below, or any direction)
  2. **% Change from Max/Min**: Alert when price moves a certain percentage from its maximum or minimum
  3. **% Move in Timeframe**: Alert when price moves a certain percentage within a specified time period
- **Continuous Alarm Sound**: Audible alerts that play until manually dismissed
- **Persistent Storage**: All settings and alarms are saved in your browser
- **Clean, Minimal Design**: Intuitive interface focused on functionality
- **Reliable Monitoring**: Continuous background monitoring with status indicator
- **Smart Price Formatting**: Automatic decimal precision based on pair type

## How to Use

### JavaScript App (Recommended for simplicity)

1. Navigate to the `javascript-app/` folder
2. Open `index.html` in your web browser
3. The app will start monitoring immediately

### Python App (For advanced features)

1. Navigate to the `python-app/` folder
2. Follow the instructions in `python-app/PYTHON_SETUP.md`
3. Run the Flask server and access via web browser

---

The following instructions apply to both applications:

### Adding Trading Pairs

1. Enter a trading pair (e.g., BTCUSDT, ETHBTC, BNBETH) in the "Add Trading Pair" field
2. Click "Add Pair" or press Enter
3. The app will fetch the current price and display the pair

**Supported Quote Currencies**: USDT, USDC, USD, BUSD, DAI, BTC, ETH, BNB, EUR, GBP

**Examples**:
- `BTCUSDT` - Bitcoin priced in Tether (stablecoin)
- `ETHBTC` - Ethereum priced in Bitcoin
- `BNBETH` - Binance Coin priced in Ethereum
- `SOLUSDC` - Solana priced in USD Coin

### Configuring Alarms

1. Click the "Alarms" button on any trading pair
2. Choose from three alarm types:

   **Target Price Alert**
   - Enter a target price (in the quote currency of the pair)
   - Example: For BTCUSDT, enter price in USDT (e.g., 50000)
   - Example: For ETHBTC, enter price in BTC (e.g., 0.055)
   - Choose direction: any, from below (going up), or from above (going down)
   - Click "Add"

   **% Change from Max/Min**
   - Enter the percentage change threshold
   - Choose: % down from max or % up from min
   - Click "Add"

   **% Move in Timeframe**
   - Enter the percentage change threshold
   - Choose direction: any, upward, or downward
   - Enter the time value and select unit:
     - **Minutes**: Short-term movements (e.g., 5% in 15 minutes)
     - **Hours**: Medium-term movements (e.g., 10% in 2 hours)
     - **Days**: Long-term movements (e.g., 20% in 3 days)
     - **Since start**: Tracks % move from when the alarm was created/last triggered
       - This alarm automatically resets after triggering and continues monitoring
       - No time value needed for this option
   - Click "Add"

3. Click "Back to Assets" to return to the main view

### When an Alarm Triggers

1. A modal will appear with alarm details
2. A continuous alarm sound will play
3. Click "DISMISS ALARM" to stop the sound and close the notification
4. Triggered alarms will be marked in the alarms list

### Managing Pairs and Alarms

- **Remove Pair**: Click the "Remove" button on any pair (this also removes all associated alarms)
- **Remove Alarm**: In the alarms view, click "Remove" on any individual alarm
- **View Alarm Count**: Each pair shows the number of configured alarms

## Technical Details

### JavaScript App
- **No Installation Required**: Pure HTML/CSS/JavaScript
- **No Server Needed**: Runs entirely in the browser
- **Data Persistence**: Uses LocalStorage to save configuration
- **Update Interval**: 15 seconds (can be adjusted in `app.js`)

### Python App
- **Backend**: Flask with Socket.IO for real-time updates
- **Data Persistence**: JSON file storage
- **Update Interval**: Configurable via backend
- **Additional Features**: Server-side monitoring and logging

### Both Apps
- **No API Key Needed**: Uses CoinGecko's free public API
- **Browser Compatibility**: Works in all modern browsers with Web Audio API support
- **Price History**: Keeps 24 hours of price data for timeframe calculations
- **Pair Calculation**: For stablecoin pairs, uses USD as proxy; for others, calculates ratio between base and quote

## Tips for Best Results

1. **Keep the tab visible**: IMPORTANT - For the most reliable alarm sound, keep the browser tab visible or use a separate window. Browser audio contexts can be suspended when tabs are inactive for extended periods.
2. **Allow audio**: Make sure your browser allows audio playback from the page. Click the "🔔 Test Alarm" button to verify sound works.
3. **Check system volume**: The alarm plays at 60% volume. Ensure your system volume is adequate.
4. **Visual alerts**: Even if you can't hear the sound, the page title will flash "🚨 ALARM TRIGGERED! 🚨" when an alarm fires.
5. **Stable connection**: Ensure a stable internet connection for reliable price updates
6. **Reasonable thresholds**: Set alarm thresholds that account for normal price volatility
7. **Test before relying**: Use the test alarm button to verify everything works before setting important alarms
8. **Check pair format**: Ensure the quote currency is one of the supported currencies

## Alarm Examples

**For BTCUSDT (stablecoin pair)**:
- **Bull Run Alert**: Target price 60000 with "from below" direction
- **Stop Loss**: 10% down from max
- **Quick Pump**: 3% up in 30 minutes
- **Hourly Volatility**: 5% move (any direction) in 2 hours
- **Daily Target**: 15% up in 1 day
- **Session Tracker**: 8% move since start (resets on trigger)

**For ETHBTC (crypto pair)**:
- **Breaking Resistance**: Target price 0.06 with "from below" direction
- **Ratio Drop Alert**: 5% down from max
- **Short-term Spike**: 2% move (any direction) in 15 minutes
- **Trending Move**: 10% up in 4 hours
- **Swing Trading**: 5% move since start (resets after each trigger)

**Max/Min Tracking Note**:
- Max/Min prices are tracked from the moment you add the pair
- They persist across app restarts (saved in browser storage)
- Reset only when you remove and re-add the pair

## Limitations

- Relies on CoinGecko API availability and rate limits
- Price updates occur every 15 seconds (not real-time tick data)
- Max/min prices reset when you remove and re-add a pair
- Timeframe alarms require sufficient price history
- Both assets in the pair must be available on CoinGecko
- Quote currency must be one of the supported currencies

## Troubleshooting

**Invalid pair format**: Make sure the pair ends with a supported quote currency (USDT, BTC, ETH, etc.)

**Base asset not found**: Verify the base token symbol exists on CoinGecko

**Quote asset not found**: Ensure quote currency is spelled correctly and supported

**No alarm sound / Sound stops playing**:
- Check browser audio permissions and system volume
- Keep the browser tab VISIBLE - browser suspends audio for inactive tabs
- Look for the flashing page title "🚨 ALARM TRIGGERED! 🚨" as a visual backup
- Open browser console (F12) and check for audio context warnings
- Use the "🔔 Test Alarm" button to verify audio is working
- If tab was inactive for a long time, the audio context may have been suspended

**Prices not updating**: Check internet connection and browser console for errors

**Alarms not triggering**: Verify alarm conditions are possible with current price action

## Privacy

All data is stored locally in your browser. No information is sent to any server except API requests to CoinGecko for price data.
