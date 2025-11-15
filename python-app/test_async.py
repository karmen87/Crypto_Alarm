from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from threading import Thread
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'test-key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', ping_timeout=60, ping_interval=25)

@app.route('/')
def index():
    return '<h1>Test Server</h1><p>Check console</p>'

@socketio.on('connect')
def handle_connect():
    print('✅ Client connected')
    emit('message', {'data': 'Connected!'})

@socketio.on('test')
def handle_test(data):
    print(f'📥 Received test request: {data}')
    
    def slow_operation():
        print('⏳ Starting 10-second operation...')
        time.sleep(10)
        print('✅ Operation complete!')
        socketio.emit('message', {'data': 'Operation complete after 10 seconds!'})
    
    Thread(target=slow_operation, daemon=True).start()
    emit('message', {'data': 'Operation started, please wait 10 seconds...'})

if __name__ == '__main__':
    print('Test server starting...')
    socketio.run(app, debug=True, host='0.0.0.0', port=5001)