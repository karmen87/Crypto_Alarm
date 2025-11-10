"""
Crypto Monitor - Using Binance API (More Reliable)
Binance has better rate limits than CoinGecko
"""

import requests
import time
import json
import os
from datetime import datetime
from threading import Thread, Lock
import uuid


class CryptoMonitorBinance:
    def __init__(self, data_file='data/crypto_data_binance.json'):
        self.data_file = data_file
        self.assets = {}
        self.alarms = {}
        self.price_history = {}
        self.lock = Lock()
        self.monitoring = False
        self.monitor_thread = None
        self.price_update_callback = None
        self.alarm_callback = None
        self.reset_timers = {}

        # Load existing data
        self.load_data()

    def load_data(self):
        """Load data from JSON file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.assets = data.get('assets', {})
                    self.alarms = data.get('alarms', {})
                    self.price_history = data.get('price_history', {})
                    print(f"Loaded {len(self.assets)} assets and {len(self.alarms)} alarms")
        except Exception as e:
            print(f"Error loading data: {e}")

    def save_data(self):
        """Save data to JSON file"""
        try:
            os.makedirs(os.path.dirname(self.data_file) if os.path.dirname(self.data_file) else '.', exist_ok=True)
            with self.lock:
                data = {
                    'assets': self.assets,
                    'alarms': self.alarms,
                    'price_history': self.price_history
                }
                with open(self.data_file, 'w') as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving data: {e}")

    def fetch_binance_price(self, symbol):
        """Fetch price from Binance API"""
        try:
            # Binance uses symbols like BTCUSDT (no separator)
            url = f'https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}'
            print(f"  Calling Binance API: {url}")
            response = requests.get(url, timeout=10)

            print(f"  Status code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                price = float(data['lastPrice'])
                print(f"  ✅ Got price: ${price:,.2f}")
                return {
                    'price': price,
                    'change24h': float(data['priceChangePercent']),
                    'high24h': float(data['highPrice']),
                    'low24h': float(data['lowPrice']),
                    'volume': float(data['volume'])
                }
            else:
                print(f"  ❌ Binance API error for {symbol}: {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"  ❌ Exception fetching Binance price for {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def add_asset(self, pair):
        """Add a new trading pair to monitor"""
        pair = pair.strip().upper()

        if not pair:
            return {'success': False, 'message': 'Please enter a trading pair'}

        if pair in self.assets:
            return {'success': False, 'message': 'Pair already added'}

        print(f"Fetching {pair} from Binance...")

        # Try to fetch the price
        price_data = self.fetch_binance_price(pair)

        if not price_data:
            return {
                'success': False,
                'message': f'Pair {pair} not found on Binance. Try: BTCUSDT, ETHUSDT, BNBUSDT, etc.'
            }

        # Parse the pair to get base and quote
        # Common quote currencies
        quotes = ['USDT', 'USDC', 'BUSD', 'BTC', 'ETH', 'BNB', 'EUR', 'GBP']
        base = None
        quote = None

        for q in quotes:
            if pair.endswith(q) and len(pair) > len(q):
                base = pair[:-len(q)]
                quote = q
                break

        if not base or not quote:
            return {'success': False, 'message': 'Could not parse trading pair'}

        # Create asset
        asset = {
            'ticker': pair,
            'base': base,
            'quote': quote,
            'name': f"{base}/{quote}",
            'price': price_data['price'],
            'change24h': price_data['change24h'],
            'maxPrice': price_data['price'],
            'minPrice': price_data['price'],
            'high24h': price_data['high24h'],
            'low24h': price_data['low24h'],
            'lastUpdate': time.time()
        }

        with self.lock:
            self.assets[pair] = asset
            self.price_history[pair] = [{'price': price_data['price'], 'timestamp': time.time()}]
            self.save_data()

        print(f"✅ Successfully added {pair}: ${price_data['price']}")
        return {'success': True, 'asset': asset}

    def remove_asset(self, ticker):
        """Remove a trading pair"""
        with self.lock:
            if ticker in self.assets:
                del self.assets[ticker]

            if ticker in self.price_history:
                del self.price_history[ticker]

            # Remove associated alarms
            alarms_to_remove = [aid for aid, alarm in self.alarms.items() if alarm['ticker'] == ticker]
            for aid in alarms_to_remove:
                del self.alarms[aid]

            self.save_data()

    def add_target_alarm(self, ticker, target_price, direction):
        """Add a target price alarm"""
        alarm_id = str(uuid.uuid4())
        alarm = {
            'id': alarm_id,
            'ticker': ticker,
            'type': 'target',
            'targetPrice': target_price,
            'direction': direction,
            'triggered': False,
            'createdAt': time.time()
        }

        with self.lock:
            self.alarms[alarm_id] = alarm
            self.save_data()

        return alarm

    def add_extreme_alarm(self, ticker, percentage, extreme_type):
        """Add a max/min percentage alarm"""
        alarm_id = str(uuid.uuid4())
        alarm = {
            'id': alarm_id,
            'ticker': ticker,
            'type': 'extreme',
            'percentage': percentage,
            'extremeType': extreme_type,
            'triggered': False,
            'createdAt': time.time()
        }

        with self.lock:
            self.alarms[alarm_id] = alarm
            self.save_data()

        return alarm

    def add_timeframe_alarm(self, ticker, percentage, direction, time_value, time_unit):
        """Add a timeframe percentage alarm"""
        alarm_id = str(uuid.uuid4())
        alarm = {
            'id': alarm_id,
            'ticker': ticker,
            'type': 'timeframe',
            'percentage': percentage,
            'direction': direction,
            'timeValue': int(time_value) if time_unit != 'since_start' else None,
            'timeUnit': time_unit,
            'triggered': False,
            'createdAt': time.time(),
            'lastResetTime': time.time()
        }

        with self.lock:
            self.alarms[alarm_id] = alarm
            self.save_data()

        return alarm

    def remove_alarm(self, alarm_id):
        """Remove an alarm"""
        with self.lock:
            if alarm_id in self.alarms:
                del self.alarms[alarm_id]
                self.save_data()

    def restart_alarm(self, alarm_id):
        """Restart a target alarm after 60 seconds"""
        with self.lock:
            if alarm_id in self.alarms:
                alarm = self.alarms[alarm_id]
                alarm['resetUntil'] = time.time() + 60
                alarm['resetting'] = True
                self.save_data()

                def reset_after_cooldown():
                    time.sleep(60)
                    with self.lock:
                        if alarm_id in self.alarms:
                            self.alarms[alarm_id]['triggered'] = False
                            self.alarms[alarm_id]['resetting'] = False
                            self.alarms[alarm_id]['resetUntil'] = None
                            self.save_data()

                Thread(target=reset_after_cooldown, daemon=True).start()

    def update_all_prices(self):
        """Update prices for all assets"""
        for ticker, asset in list(self.assets.items()):
            try:
                price_data = self.fetch_binance_price(ticker)

                if price_data:
                    with self.lock:
                        asset['price'] = price_data['price']
                        asset['change24h'] = price_data['change24h']
                        asset['lastUpdate'] = time.time()

                        # Update max/min
                        if price_data['price'] > asset['maxPrice']:
                            asset['maxPrice'] = price_data['price']
                        if price_data['price'] < asset['minPrice']:
                            asset['minPrice'] = price_data['price']

                        # Update price history
                        if ticker not in self.price_history:
                            self.price_history[ticker] = []

                        self.price_history[ticker].append({
                            'price': price_data['price'],
                            'timestamp': time.time()
                        })

                        # Keep only last 24 hours
                        cutoff = time.time() - (24 * 60 * 60)
                        self.price_history[ticker] = [
                            h for h in self.price_history[ticker] if h['timestamp'] > cutoff
                        ]

                        self.assets[ticker] = asset

            except Exception as e:
                print(f"Error updating price for {ticker}: {e}")

        self.save_data()

    def check_alarms(self):
        """Check all alarms for trigger conditions"""
        triggered_alarms = []

        for alarm_id, alarm in list(self.alarms.items()):
            if alarm.get('triggered') and not alarm.get('resetting'):
                continue

            ticker = alarm['ticker']
            if ticker not in self.assets:
                continue

            asset = self.assets[ticker]
            should_trigger = False
            message = ''
            direction = None

            try:
                if alarm['type'] == 'target':
                    should_trigger, direction = self.check_target_alarm(alarm, asset)
                    if should_trigger:
                        message = f"{asset['name']} ({ticker}) reached target price of ${alarm['targetPrice']:.2f}!"

                elif alarm['type'] == 'extreme':
                    should_trigger, direction = self.check_extreme_alarm(alarm, asset)
                    if should_trigger:
                        message = f"{asset['name']} ({ticker}) hit extreme price level!"

                elif alarm['type'] == 'timeframe':
                    should_trigger, direction = self.check_timeframe_alarm(alarm, asset)
                    if should_trigger:
                        message = f"{asset['name']} ({ticker}) hit timeframe target!"

                if should_trigger:
                    if alarm['type'] == 'timeframe' and alarm['timeUnit'] == 'since_start':
                        with self.lock:
                            self.alarms[alarm_id]['lastResetTime'] = time.time()
                            self.save_data()
                    else:
                        with self.lock:
                            self.alarms[alarm_id]['triggered'] = True
                            self.alarms[alarm_id]['triggeredAt'] = time.time()
                            self.save_data()

                    triggered_alarms.append({
                        'alarm': alarm,
                        'asset': asset,
                        'message': message,
                        'direction': direction
                    })

            except Exception as e:
                print(f"Error checking alarm {alarm_id}: {e}")

        return triggered_alarms

    def check_target_alarm(self, alarm, asset):
        """Check if target price alarm should trigger"""
        current_price = asset['price']
        target_price = alarm['targetPrice']
        eps = max(1e-8, abs(target_price) * 1e-6)

        ticker = alarm['ticker']
        history = self.price_history.get(ticker, [])

        if len(history) < 2:
            if alarm['direction'] == 'up':
                return current_price + eps >= target_price, 'up'
            elif alarm['direction'] == 'down':
                return current_price - eps <= target_price, 'down'
            else:
                return abs(current_price - target_price) <= eps, None

        previous_price = history[-2]['price']

        if alarm['direction'] == 'up':
            if previous_price < target_price and current_price + eps >= target_price:
                return True, 'up'
        elif alarm['direction'] == 'down':
            if previous_price > target_price and current_price - eps <= target_price:
                return True, 'down'
        else:
            if (previous_price < target_price and current_price + eps >= target_price) or \
               (previous_price > target_price and current_price - eps <= target_price):
                return True, 'up' if current_price >= target_price else 'down'

        return False, None

    def check_extreme_alarm(self, alarm, asset):
        """Check if extreme (max/min) alarm should trigger"""
        current_price = asset['price']

        if alarm['extremeType'] == 'max':
            max_price = asset['maxPrice']
            percent_down = ((max_price - current_price) / max_price) * 100
            if percent_down >= alarm['percentage']:
                return True, 'down'
        else:
            min_price = asset['minPrice']
            percent_up = ((current_price - min_price) / min_price) * 100
            if percent_up >= alarm['percentage']:
                return True, 'up'

        return False, None

    def check_timeframe_alarm(self, alarm, asset):
        """Check if timeframe alarm should trigger"""
        ticker = alarm['ticker']
        history = self.price_history.get(ticker, [])

        if len(history) < 2:
            return False, None

        current_time = time.time()

        if alarm['timeUnit'] == 'since_start':
            start_time = alarm.get('lastResetTime', alarm['createdAt'])
        else:
            time_value = alarm['timeValue']
            if alarm['timeUnit'] == 'minutes':
                timeframe_seconds = time_value * 60
            elif alarm['timeUnit'] == 'hours':
                timeframe_seconds = time_value * 60 * 60
            elif alarm['timeUnit'] == 'days':
                timeframe_seconds = time_value * 24 * 60 * 60
            else:
                timeframe_seconds = time_value * 60

            start_time = current_time - timeframe_seconds

        relevant_history = [h for h in history if h['timestamp'] >= start_time]

        if not relevant_history:
            return False, None

        start_price = relevant_history[0]['price']
        current_price = asset['price']
        percent_change = ((current_price - start_price) / start_price) * 100

        if alarm['direction'] == 'up':
            if percent_change >= alarm['percentage']:
                return True, 'up'
        elif alarm['direction'] == 'down':
            if percent_change <= -alarm['percentage']:
                return True, 'down'
        else:
            if abs(percent_change) >= alarm['percentage']:
                return True, 'up' if percent_change > 0 else 'down'

        return False, None

    def monitoring_loop(self):
        """Main monitoring loop"""
        print("📊 Monitoring started (Binance API)")
        while self.monitoring:
            try:
                self.update_all_prices()
                triggered = self.check_alarms()

                if self.price_update_callback:
                    self.price_update_callback({
                        'assets': self.get_assets(),
                        'alarms': self.get_alarms()
                    })

                if triggered and self.alarm_callback:
                    for alarm_data in triggered:
                        self.alarm_callback(alarm_data)

            except Exception as e:
                print(f"Error in monitoring loop: {e}")

            time.sleep(10)  # Update every 10 seconds

        print("Monitoring stopped")

    def start_monitoring(self):
        """Start the monitoring thread"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = Thread(target=self.monitoring_loop, daemon=True)
            self.monitor_thread.start()

    def stop_monitoring(self):
        """Stop the monitoring thread"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

    def set_price_update_callback(self, callback):
        """Set callback for price updates"""
        self.price_update_callback = callback

    def set_alarm_callback(self, callback):
        """Set callback for alarm triggers"""
        self.alarm_callback = callback

    def get_assets(self):
        """Get all assets"""
        with self.lock:
            return dict(self.assets)

    def get_alarms(self):
        """Get all alarms"""
        with self.lock:
            return dict(self.alarms)
