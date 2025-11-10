"""
Crypto Price Alarm - Using Binance API (Reliable, Real Prices)
"""

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from crypto_monitor_binance import CryptoMonitorBinance
from threading import Thread

app = Flask(__name__)
app.config['SECRET_KEY'] = 'binance-crypto-alarm'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', ping_timeout=60, ping_interval=25)

# Initialize the crypto monitor with Binance
monitor = CryptoMonitorBinance()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print('✅ Client connected')
    emit('initial_state', {
        'assets': monitor.get_assets(),
        'alarms': monitor.get_alarms()
    })

@socketio.on('disconnect')
def handle_disconnect():
    print('❌ Client disconnected')

@socketio.on('add_asset')
def handle_add_asset(data):
    """Add a new trading pair - runs synchronously with proper context"""
    pair = data.get('pair', '').strip().upper()
    print(f"📥 Request to add: {pair}")

    try:
        # Run directly (synchronously) - Binance API is fast enough
        result = monitor.add_asset(pair)
        print(f"📤 Result: {result.get('success')}")

        if result['success']:
            emit('asset_added', result, broadcast=True)
            print(f"✅ Emitted success for {pair}")
        else:
            emit('error', {'message': result['message']})
            print(f"⚠️ Emitted error: {result['message']}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': str(e)})

@socketio.on('remove_asset')
def handle_remove_asset(data):
    ticker = data.get('ticker')
    try:
        monitor.remove_asset(ticker)
        emit('asset_removed', {'ticker': ticker}, broadcast=True)
    except Exception as e:
        print(f"❌ Error: {e}")
        emit('error', {'message': str(e)})

@socketio.on('add_alarm')
def handle_add_alarm(data):
    try:
        alarm_type = data.get('type')
        ticker = data.get('ticker')

        if alarm_type == 'target':
            alarm = monitor.add_target_alarm(
                ticker,
                float(data.get('targetPrice')),
                data.get('direction')
            )
        elif alarm_type == 'extreme':
            alarm = monitor.add_extreme_alarm(
                ticker,
                float(data.get('percentage')),
                data.get('extremeType')
            )
        elif alarm_type == 'timeframe':
            alarm = monitor.add_timeframe_alarm(
                ticker,
                float(data.get('percentage')),
                data.get('direction'),
                data.get('timeValue'),
                data.get('timeUnit')
            )
        else:
            emit('error', {'message': 'Invalid alarm type'})
            return

        emit('alarm_added', {'alarm': alarm}, broadcast=True)
    except Exception as e:
        print(f"❌ Error: {e}")
        emit('error', {'message': str(e)})

@socketio.on('remove_alarm')
def handle_remove_alarm(data):
    alarm_id = data.get('alarmId')
    try:
        monitor.remove_alarm(alarm_id)
        emit('alarm_removed', {'alarmId': alarm_id}, broadcast=True)
    except Exception as e:
        print(f"❌ Error: {e}")
        emit('error', {'message': str(e)})

@socketio.on('restart_alarm')
def handle_restart_alarm(data):
    alarm_id = data.get('alarmId')
    try:
        monitor.restart_alarm(alarm_id)
        emit('alarm_restarted', {'alarmId': alarm_id}, broadcast=True)
    except Exception as e:
        print(f"❌ Error: {e}")
        emit('error', {'message': str(e)})

def price_update_callback(update_data):
    """Callback for price updates"""
    socketio.emit('price_update', update_data)

def alarm_triggered_callback(alarm_data):
    """Callback when an alarm is triggered"""
    socketio.emit('alarm_triggered', alarm_data)

# Set callbacks
monitor.set_price_update_callback(price_update_callback)
monitor.set_alarm_callback(alarm_triggered_callback)

# Start monitoring
monitor.start_monitoring()

if __name__ == '__main__':
    print("=" * 70)
    print("🚀 Crypto Price Alarm - BINANCE API (Real Prices)")
    print("=" * 70)
    print("📍 Open http://localhost:5000 in your browser")
    print("")
    print("✅ Uses Binance API - more reliable than CoinGecko")
    print("✅ Real-time prices updated every 10 seconds")
    print("✅ Better rate limits - can add pairs quickly")
    print("")
    print("Popular pairs to try:")
    print("  • BTCUSDT - Bitcoin/USDT")
    print("  • ETHUSDT - Ethereum/USDT")
    print("  • BNBUSDT - Binance Coin/USDT")
    print("  • ADAUSDT - Cardano/USDT")
    print("  • SOLUSDT - Solana/USDT")
    print("  • DOGEUSDT - Dogecoin/USDT")
    print("")
    print("=" * 70)

    socketio.run(app, debug=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
