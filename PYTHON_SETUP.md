# Crypto Price Alarm - Python Flask Application

A real-time cryptocurrency price monitoring and alarm system built with Flask and WebSockets.

## Features

- **Real-time Price Tracking**: Monitor cryptocurrency trading pairs with live price updates every 15 seconds
- **Multiple Alarm Types**:
  - Target Price Alerts (with directional triggers)
  - Percentage Change from Max/Min
  - Percentage Move in Timeframe
- **WebSocket Communication**: Real-time updates without page refresh
- **Persistent Storage**: All data saved to JSON file
- **Audio Alarms**: Continuous sound alerts when price targets are hit
- **Clean Web Interface**: Modern, responsive design

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- A modern web browser (Chrome, Firefox, Safari, Edge)

## Installation

### 1. Navigate to the project directory

```bash
cd Crypto_Alarm
```

### 2. Create a virtual environment (recommended)

**On Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

## Running the Application

### 1. Start the Flask server

```bash
python app.py
```

You should see output like:
```
Starting Crypto Price Alarm server...
Open http://localhost:5000 in your browser
 * Running on http://0.0.0.0:5000
```

### 2. Open your browser

Navigate to:
```
http://localhost:5000
```

The application should now be running!

## Usage

### Adding Trading Pairs

1. Enter a trading pair in the format: `BASEQUOTE`
   - Examples: `BTCUSDT`, `ETHBTC`, `BNBETH`, `SOLUSDC`
2. Click "Add Pair" or press Enter
3. The app will fetch the current price and start monitoring

**Supported Quote Currencies**: USDT, USDC, USD, BUSD, DAI, BTC, ETH, BNB, EUR, GBP

### Setting Up Alarms

1. Click the "Alarms" button on any trading pair
2. Choose from three alarm types:

   **Target Price Alert**
   - Enter a target price
   - Choose direction: any, from below (going up), or from above (going down)
   - Click "Add"

   **% Change from Max/Min**
   - Enter the percentage threshold
   - Choose: % down from max or % up from min
   - Click "Add"

   **% Move in Timeframe**
   - Enter the percentage change threshold
   - Choose direction: any, upward, or downward
   - Select timeframe: minutes, hours, days, or "since start"
   - Click "Add"

3. Click "Back to Assets" to return to the main view

### When an Alarm Triggers

- A modal window will appear with alarm details
- A continuous alarm sound will play
- The page title will flash to get your attention
- Click "DISMISS ALARM" to stop the sound
- For target alarms, you can click "RESTART (60s)" to reset the alarm after a cooldown

## Project Structure

```
Crypto_Alarm/
├── app.py                 # Main Flask application
├── crypto_monitor.py      # Price monitoring and alarm logic
├── requirements.txt       # Python dependencies
├── data/
│   └── crypto_data.json  # Persistent storage (auto-created)
├── templates/
│   └── index.html        # HTML template
└── static/
    ├── css/
    │   └── styles.css    # Styling
    └── js/
        └── app.js        # Client-side WebSocket logic
```

## Technical Details

### Backend (Python)

- **Flask**: Web framework
- **Flask-SocketIO**: Real-time WebSocket communication
- **requests**: HTTP library for CoinGecko API calls
- **Threading**: Background monitoring loop

### Frontend (JavaScript)

- **Socket.IO Client**: Real-time communication with server
- **Web Audio API**: Alarm sound generation
- **LocalStorage**: Not used (replaced with server-side JSON storage)

### Data Flow

1. Client connects via WebSocket
2. Server sends initial state (assets & alarms)
3. Background thread updates prices every 15 seconds
4. Server checks alarm conditions and broadcasts updates
5. Client receives updates and renders UI
6. When alarm triggers, server notifies all connected clients

## API Rate Limiting

The application respects CoinGecko's free API rate limits:
- Minimum 1.2 seconds between API calls
- Automatic retry with backoff on rate limit errors
- For many pairs, consider using a CoinGecko API key (requires code modification)

## Troubleshooting

### Port already in use

If port 5000 is already in use, you can change it in `app.py`:

```python
socketio.run(app, debug=True, host='0.0.0.0', port=8080)  # Change to any available port
```

### Alarm sound not working

- Make sure your browser allows audio playback
- Click anywhere on the page first (browsers require user interaction to play audio)
- Use the "🔔 Test Alarm" button to verify audio works
- Keep the browser tab visible (inactive tabs may suspend audio)

### Prices not updating

- Check your internet connection
- Verify CoinGecko API is accessible
- Check the terminal for error messages
- Ensure you're not hitting API rate limits

### Module not found errors

Make sure you've activated the virtual environment and installed all dependencies:

```bash
source venv/bin/activate  # On Linux/Mac
pip install -r requirements.txt
```

## Stopping the Application

To stop the server:
1. Go to the terminal where the app is running
2. Press `Ctrl+C`
3. Deactivate the virtual environment (optional):
   ```bash
   deactivate
   ```

## Data Persistence

All your trading pairs, alarms, and price history are saved to:
```
data/crypto_data.json
```

This file is automatically created and updated. You can delete it to reset all data.

## Development Mode

The app runs in debug mode by default, which:
- Auto-reloads on code changes
- Provides detailed error messages
- Should NOT be used in production

To disable debug mode, edit `app.py`:
```python
socketio.run(app, debug=False, host='0.0.0.0', port=5000)
```

## Future Enhancements

Potential improvements:
- Database support (PostgreSQL, MongoDB)
- User authentication and multi-user support
- Email/SMS notifications
- More exchanges (Binance, Coinbase, etc.)
- Historical price charts
- Custom alert sounds
- Mobile app

## License

This project is open source. Feel free to modify and distribute.

## Credits

- Price data provided by [CoinGecko API](https://www.coingecko.com/api)
- Built with Flask, Socket.IO, and vanilla JavaScript

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the console/terminal for error messages
3. Ensure all dependencies are correctly installed

Happy monitoring! 🚀📈
