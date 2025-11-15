"""
Crypto Price Alarm - Flask Application
A real-time cryptocurrency price monitoring and alarm system
"""

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from crypto_monitor import CryptoMonitor
import json
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize the crypto monitor
monitor = CryptoMonitor()

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    # Send current state to newly connected client
    emit('initial_state', {
        'assets': monitor.get_assets(),
        'alarms': monitor.get_alarms()
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')

@socketio.on('add_asset')
def handle_add_asset(data):
    """Add a new trading pair to monitor"""
    pair = data.get('pair', '').strip().upper()

    try:
        result = monitor.add_asset(pair)
        if result['success']:
            emit('asset_added', result, broadcast=True)
        else:
            emit('error', {'message': result['message']})
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('remove_asset')
def handle_remove_asset(data):
    """Remove a trading pair"""
    ticker = data.get('ticker')

    try:
        monitor.remove_asset(ticker)
        emit('asset_removed', {'ticker': ticker}, broadcast=True)
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('add_alarm')
def handle_add_alarm(data):
    """Add a new alarm"""
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
        emit('error', {'message': str(e)})

@socketio.on('remove_alarm')
def handle_remove_alarm(data):
    """Remove an alarm"""
    alarm_id = data.get('alarmId')

    try:
        monitor.remove_alarm(alarm_id)
        emit('alarm_removed', {'alarmId': alarm_id}, broadcast=True)
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('restart_alarm')
def handle_restart_alarm(data):
    """Restart a target alarm (reset it after trigger)"""
    alarm_id = data.get('alarmId')

    try:
        monitor.restart_alarm(alarm_id)
        emit('alarm_restarted', {'alarmId': alarm_id}, broadcast=True)
    except Exception as e:
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
    print("Starting Crypto Price Alarm server...")
    print("Open http://localhost:5000 in your browser")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
