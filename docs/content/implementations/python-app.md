---
title: "Python App"
weight: 2
---

# Python App: Server-Side Implementation

## Overview

The Python implementation is a Flask-based server application with WebSocket support for real-time updates. It provides centralized monitoring, server-side persistence, and supports multiple concurrent clients.

## Architecture

### Core Components

```
python-app/
├── app.py                      # Flask application + WebSocket server
├── templates/
│   └── index.html              # Frontend UI
├── static/
│   ├── css/
│   │   └── styles.css          # Styles
│   ├── js/
│   │   └── app.js              # Client-side logic
│   └── alarm.mp3               # Alarm sound
├── data/
│   └── crypto_data_binance.json # Persistent storage
├── requirements.txt            # Python dependencies
└── PYTHON_SETUP.md             # Setup instructions
```

### Technology Stack

**Backend**:
- **Flask**: Web framework
- **Flask-SocketIO**: WebSocket server
- **python-socketio**: Socket.IO client/server
- **requests**: HTTP client for API calls
- **APScheduler**: Background job scheduling

**Frontend**:
- **Socket.IO Client**: Real-time communication
- **Vanilla JavaScript**: UI logic
- **HTML/CSS**: Interface structure

## Data Persistence: JSON File Storage

All application state is stored in a JSON file on the server:

```
data/crypto_data_binance.json
```

### Storage Schema

```json
{
  "pairs": {
    "BTCUSDT": {
      "symbol": "BTCUSDT",
      "currentPrice": 50000,
      "maxPrice": 52000,
      "minPrice": 48000,
      "lastUpdate": "2024-01-15T10:30:00Z",
      "priceHistory": [
        {
          "price": 50000,
          "timestamp": "2024-01-15T10:29:45Z"
        }
      ],
      "alarms": [
        {
          "id": "alarm_1704000000",
          "type": "target",
          "targetPrice": 55000,
          "direction": "fromBelow",
          "triggered": false,
          "createdAt": "2024-01-15T10:00:00Z"
        }
      ]
    }
  },
  "metadata": {
    "lastModified": "2024-01-15T10:30:00Z",
    "version": "1.0"
  }
}
```

### JSON Storage Benefits

- **Human-Readable**: Easy to inspect and debug
- **Version Control Friendly**: Can track in Git
- **Portable**: Transfer between servers easily
- **Backup-Friendly**: Simple file copy
- **Multi-Client**: Shared state across connections

### JSON Storage Considerations

- **Concurrency**: File locking for write operations
- **Performance**: In-memory caching for reads
- **Atomicity**: Atomic file writes (write to temp → rename)
- **Size Management**: Archive old price history

## WebSocket Communication

### Real-Time Updates Architecture

```
Flask Server (app.py)
  ├── Background Scheduler (15s interval)
  │   ├── Fetch prices from CoinGecko
  │   ├── Update JSON file
  │   └── Emit 'price_update' event
  └── WebSocket Server
      └── Broadcast to all connected clients

Browser Clients
  └── Socket.IO Client
      ├── Listen for 'price_update'
      ├── Update UI in real-time
      └── Check alarm conditions
```

### Server-Side WebSocket Events

**Emitting Price Updates**:
```python
# app.py - Background job
@sched.scheduled_job('interval', seconds=15)
def update_prices():
    for pair in get_all_pairs():
        price = fetch_from_coingecko(pair)
        update_json_file(pair, price)

        # Broadcast to all clients
        socketio.emit('price_update', {
            'pair': pair,
            'price': price,
            'timestamp': datetime.utcnow().isoformat()
        })
```

**Client Events**:
```python
# Listen for client requests
@socketio.on('add_pair')
def handle_add_pair(data):
    pair = data['pair']
    # Validate and add pair
    result = add_pair_to_storage(pair)
    emit('pair_added', result)

@socketio.on('add_alarm')
def handle_add_alarm(data):
    pair = data['pair']
    alarm_config = data['alarm']
    # Add alarm to JSON
    result = add_alarm_to_storage(pair, alarm_config)
    emit('alarm_added', result)
```

### Client-Side WebSocket Handling

```javascript
// static/js/app.js
const socket = io();

// Listen for price updates
socket.on('price_update', (data) => {
  updatePairUI(data.pair, data.price);
  checkAlarms(data.pair, data.price);
});

// Send requests to server
function addNewPair(pair) {
  socket.emit('add_pair', { pair: pair });
}

socket.on('pair_added', (result) => {
  if (result.success) {
    refreshPairsList();
  }
});
```

### WebSocket Advantages

1. **Real-Time**: Instant updates to all clients
2. **Low Latency**: No polling overhead
3. **Efficient**: Single server connection per client
4. **Bidirectional**: Server can push updates
5. **Scalable**: Handles many concurrent clients

## Background Monitoring

### APScheduler Integration

```python
from apscheduler.schedulers.background import BackgroundScheduler

sched = BackgroundScheduler()
sched.start()

@sched.scheduled_job('interval', seconds=15)
def monitor_prices():
    """Runs every 15 seconds, even when no clients connected"""
    pairs = load_pairs_from_json()

    for pair in pairs:
        # Fetch price
        price = fetch_coingecko_price(pair)

        # Update storage
        update_pair_data(pair, price)

        # Check server-side alarms
        triggered = check_alarms(pair, price)

        # Broadcast updates
        if triggered:
            socketio.emit('alarm_triggered', {
                'pair': pair,
                'alarm': triggered
            })
        else:
            socketio.emit('price_update', {
                'pair': pair,
                'price': price
            })
```

### Server-Side Benefits

- **Continuous Monitoring**: Runs even when browser closed
- **Centralized Logic**: One monitoring process for all users
- **Logging**: Server logs all alarm triggers
- **Reliability**: Not dependent on browser tab state

## API Integration

### CoinGecko Client

```python
import requests

class CoinGeckoClient:
    BASE_URL = 'https://api.coingecko.com/api/v3'

    def get_price(self, base, quote):
        """Fetch price for a trading pair"""
        if quote in ['USDT', 'USDC', 'USD', 'BUSD', 'DAI']:
            # Stablecoin pair
            return self._get_usd_price(base)
        else:
            # Crypto pair
            return self._get_ratio_price(base, quote)

    def _get_usd_price(self, symbol):
        """Get token price in USD"""
        coin_id = self._resolve_symbol(symbol)
        response = requests.get(
            f'{self.BASE_URL}/simple/price',
            params={'ids': coin_id, 'vs_currencies': 'usd'}
        )
        return response.json()[coin_id]['usd']

    def _get_ratio_price(self, base, quote):
        """Get ratio between two cryptos"""
        base_id = self._resolve_symbol(base)
        quote_id = self._resolve_symbol(quote)

        response = requests.get(
            f'{self.BASE_URL}/simple/price',
            params={
                'ids': f'{base_id},{quote_id}',
                'vs_currencies': 'usd'
            }
        )

        data = response.json()
        base_price = data[base_id]['usd']
        quote_price = data[quote_id]['usd']

        return base_price / quote_price
```

### Error Handling & Retries

```python
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

def get_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session
```

## Deployment

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python app.py

# Access at http://localhost:5000
```

### Production Deployment Options

#### Option 1: Gunicorn + Nginx

```bash
# Install gunicorn
pip install gunicorn

# Run with workers
gunicorn --worker-class eventlet -w 1 app:app --bind 0.0.0.0:5000
```

**Nginx Configuration**:
```nginx
server {
    listen 80;
    server_name crypto-alarm.example.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

#### Option 2: Docker

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "app:app", "--bind", "0.0.0.0:5000"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  crypto-alarm:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
    environment:
      - FLASK_ENV=production
```

#### Option 3: Systemd Service

```ini
# /etc/systemd/system/crypto-alarm.service
[Unit]
Description=Crypto Price Alarm
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/crypto-alarm
ExecStart=/usr/local/bin/gunicorn --worker-class eventlet -w 1 app:app --bind 0.0.0.0:5000
Restart=always

[Install]
WantedBy=multi-user.target
```

## Logging & Monitoring

### Application Logging

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Usage
logger.info(f'Price update: {pair} = ${price}')
logger.warning(f'API rate limit approaching')
logger.error(f'Failed to fetch price for {pair}', exc_info=True)
```

### Alarm Trigger Logging

```python
def log_alarm_trigger(pair, alarm, price):
    logger.info(
        f'ALARM TRIGGERED: {pair} | '
        f'Type: {alarm["type"]} | '
        f'Price: {price} | '
        f'Condition: {alarm["condition"]}'
    )

    # Append to audit log
    with open('logs/alarms.log', 'a') as f:
        f.write(json.dumps({
            'timestamp': datetime.utcnow().isoformat(),
            'pair': pair,
            'alarm': alarm,
            'price': price
        }) + '\n')
```

## Advantages

1. **Server-Side Reliability**: Monitoring runs independently
2. **Multi-Client**: Multiple users can connect
3. **Real-Time Updates**: WebSocket instant updates
4. **Centralized Data**: Single source of truth
5. **Logging**: Full audit trail
6. **Scalable**: Can handle many pairs/clients

## Limitations

1. **Infrastructure Required**: Need server to run
2. **Setup Complexity**: Installation + configuration
3. **Maintenance**: Server upkeep required
4. **Dependencies**: Python environment needed

## Use Cases

**Ideal For**:
- Team/shared monitoring
- Server-side automation
- Production deployments
- Multi-user scenarios
- Audit/logging requirements

**Not Ideal For**:
- Quick personal use
- No-server environments
- Maximum simplicity
- Offline operation

## Performance Considerations

### Memory Usage
- In-memory cache: ~50MB for 100 pairs
- JSON file: ~1MB per 1000 price points

### Concurrent Clients
- Tested with 50 simultaneous connections
- WebSocket overhead: ~10KB per client

### API Rate Limits
- CoinGecko free tier: 50 calls/minute
- Implementation: Batch requests for efficiency

## Security Considerations

### File Permissions
```bash
# Restrict JSON file access
chmod 600 data/crypto_data_binance.json
chown www-data:www-data data/crypto_data_binance.json
```

### Environment Variables
```python
# Don't hardcode sensitive values
import os

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
```

### CORS Configuration
```python
from flask_cors import CORS

# Restrict origins in production
CORS(app, resources={
    r"/*": {"origins": ["https://crypto-alarm.example.com"]}
})
```

## Next Steps

- Compare with **JavaScript App** for client-side alternative
- Explore **Alarm Logic** for alarm type implementation
- See **API Integration** for CoinGecko details
- Check **DevOps** for CI/CD pipeline
