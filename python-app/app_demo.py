"""
Crypto Price Alarm - DEMO VERSION with Mock Data
This version uses fake data so you can test the app without API issues
"""

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import random
import time
from threading import Thread
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'demo-key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Mock data
assets = {}
alarms = {}
monitoring = True

# Fake crypto data
MOCK_CRYPTOS = {
    'BTCUSDT': {'name': 'Bitcoin/USDT', 'base_price': 50000},
    'ETHUSDT': {'name': 'Ethereum/USDT', 'base_price': 3000},
    'BNBUSDT': {'name': 'Binance Coin/USDT', 'base_price': 400},
    'SOLUSDT': {'name': 'Solana/USDT', 'base_price': 100},
    'ADAUSDT': {'name': 'Cardano/USDT', 'base_price': 0.5},
}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print('✅ Client connected')
    emit('initial_state', {'assets': assets, 'alarms': alarms})

@socketio.on('disconnect')
def handle_disconnect():
    print('❌ Client disconnected')

@socketio.on('add_asset')
def handle_add_asset(data):
    pair = data.get('pair', '').strip().upper()
    print(f"📥 Adding mock pair: {pair}")

    # Simulate API delay
    time.sleep(1)

    if pair in assets:
        emit('error', {'message': 'Pair already added'})
        return

    if pair not in MOCK_CRYPTOS:
        emit('error', {'message': f'{pair} not found. Try: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, or ADAUSDT'})
        return

    mock = MOCK_CRYPTOS[pair]
    price = mock['base_price'] * random.uniform(0.95, 1.05)

    assets[pair] = {
        'ticker': pair,
        'name': mock['name'],
        'base': pair[:-4],
        'quote': 'USDT',
        'price': price,
        'change24h': random.uniform(-5, 5),
        'maxPrice': price,
        'minPrice': price,
        'lastUpdate': time.time()
    }

    socketio.emit('asset_added', {'success': True, 'asset': assets[pair]})
    print(f"✅ Added {pair}")

@socketio.on('remove_asset')
def handle_remove_asset(data):
    ticker = data.get('ticker')
    if ticker in assets:
        del assets[ticker]
        # Remove associated alarms
        to_remove = [aid for aid, alarm in alarms.items() if alarm['ticker'] == ticker]
        for aid in to_remove:
            del alarms[aid]
        emit('asset_removed', {'ticker': ticker}, broadcast=True)

@socketio.on('add_alarm')
def handle_add_alarm(data):
    alarm_type = data.get('type')
    ticker = data.get('ticker')

    alarm_id = f"alarm_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"

    alarm = {
        'id': alarm_id,
        'ticker': ticker,
        'type': alarm_type,
        'triggered': False,
        'createdAt': time.time()
    }

    if alarm_type == 'target':
        alarm['targetPrice'] = float(data.get('targetPrice'))
        alarm['direction'] = data.get('direction')
    elif alarm_type == 'extreme':
        alarm['percentage'] = float(data.get('percentage'))
        alarm['extremeType'] = data.get('extremeType')
    elif alarm_type == 'timeframe':
        alarm['percentage'] = float(data.get('percentage'))
        alarm['direction'] = data.get('direction')
        alarm['timeValue'] = data.get('timeValue')
        alarm['timeUnit'] = data.get('timeUnit')

    alarms[alarm_id] = alarm
    emit('alarm_added', {'alarm': alarm}, broadcast=True)

@socketio.on('remove_alarm')
def handle_remove_alarm(data):
    alarm_id = data.get('alarmId')
    if alarm_id in alarms:
        del alarms[alarm_id]
        emit('alarm_removed', {'alarmId': alarm_id}, broadcast=True)

def monitoring_loop():
    """Update prices every 5 seconds with random fluctuations"""
    print("📊 Price monitoring started (mock data)")

    while monitoring:
        try:
            if assets:
                for ticker, asset in assets.items():
                    # Random price movement
                    change = random.uniform(-0.02, 0.02)  # ±2%
                    asset['price'] *= (1 + change)
                    asset['change24h'] += random.uniform(-0.5, 0.5)

                    # Update max/min
                    if asset['price'] > asset['maxPrice']:
                        asset['maxPrice'] = asset['price']
                    if asset['price'] < asset['minPrice']:
                        asset['minPrice'] = asset['price']

                    asset['lastUpdate'] = time.time()

                # Send updates to clients
                socketio.emit('price_update', {'assets': assets, 'alarms': alarms})

                # Check alarms (simplified)
                for alarm_id, alarm in list(alarms.items()):
                    if alarm['triggered']:
                        continue

                    asset = assets.get(alarm['ticker'])
                    if not asset:
                        continue

                    # Simple target price check
                    if alarm['type'] == 'target':
                        target = alarm['targetPrice']
                        current = asset['price']

                        if abs(current - target) / target < 0.01:  # Within 1%
                            alarm['triggered'] = True
                            direction = 'up' if current >= target else 'down'

                            socketio.emit('alarm_triggered', {
                                'alarm': alarm,
                                'asset': asset,
                                'message': f"{asset['name']} reached ${current:.2f} (target: ${target:.2f})",
                                'direction': direction
                            })
                            print(f"🚨 ALARM TRIGGERED: {ticker} @ ${current:.2f}")

        except Exception as e:
            print(f"Error in monitoring: {e}")

        time.sleep(5)  # Update every 5 seconds

if __name__ == '__main__':
    print("=" * 70)
    print("🎮 CRYPTO PRICE ALARM - DEMO MODE (Mock Data)")
    print("=" * 70)
    print("📍 Open http://localhost:5000 in your browser")
    print("")
    print("ℹ️  This demo uses FAKE data to test the app without API issues")
    print("")
    print("Available pairs to add:")
    for pair, info in MOCK_CRYPTOS.items():
        print(f"  • {pair} - {info['name']}")
    print("")
    print("Prices update every 5 seconds with random fluctuations")
    print("=" * 70)

    # Start monitoring thread
    Thread(target=monitoring_loop, daemon=True).start()

    socketio.run(app, debug=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
