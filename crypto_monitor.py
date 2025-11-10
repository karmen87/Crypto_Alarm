"""
Crypto Monitor - Core monitoring and alarm logic
"""

import requests
import time
import json
import os
from datetime import datetime, timedelta
from threading import Thread, Lock
import uuid


class CryptoMonitor:
    def __init__(self, data_file='data/crypto_data.json'):
        self.data_file = data_file
        self.assets = {}
        self.alarms = {}
        self.price_history = {}
        self.lock = Lock()
        self.monitoring = False
        self.monitor_thread = None
        self.price_update_callback = None
        self.alarm_callback = None
        self.last_api_call = 0
        self.min_api_delay = 2.0  # Increased to 2 seconds to avoid rate limits
        self.reset_timers = {}  # For alarm reset cooldowns

        # Supported quote currencies
        self.quote_currencies = ['USDT', 'USDC', 'USD', 'BUSD', 'DAI', 'BTC', 'ETH', 'BNB', 'EUR', 'GBP']
        self.stablecoins = ['USDT', 'USDC', 'USD', 'BUSD', 'DAI', 'TUSD', 'USDD', 'USDP']

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

    def parse_trading_pair(self, pair_string):
        """Parse a trading pair string into base and quote"""
        pair_string = pair_string.upper().strip()

        for quote in self.quote_currencies:
            if pair_string.endswith(quote) and len(pair_string) > len(quote):
                base = pair_string[:-len(quote)]
                return {'base': base, 'quote': quote, 'pair': pair_string}

        return None

    def is_stablecoin(self, symbol):
        """Check if a symbol is a stablecoin"""
        return symbol.upper() in self.stablecoins

    async def wait_for_rate_limit(self):
        """Rate limiting for API calls"""
        now = time.time()
        time_since_last = now - self.last_api_call

        if time_since_last < self.min_api_delay:
            wait_time = self.min_api_delay - time_since_last
            time.sleep(wait_time)

        self.last_api_call = time.time()

    def fetch_coin_id(self, ticker):
        """Fetch CoinGecko coin ID from ticker symbol"""
        try:
            time.sleep(max(0, self.min_api_delay - (time.time() - self.last_api_call)))
            self.last_api_call = time.time()

            url = f'https://api.coingecko.com/api/v3/search?query={ticker}'
            response = requests.get(url, timeout=10)

            if response.status_code == 429:
                print(f'⚠️  Rate limited by CoinGecko API for ticker: {ticker}')
                print('   Please wait a minute before trying again.')
                return None

            data = response.json()

            for coin in data.get('coins', []):
                if coin['symbol'].lower() == ticker.lower():
                    return {
                        'id': coin['id'],
                        'name': coin['name'],
                        'symbol': coin['symbol']
                    }

            return None
        except Exception as e:
            print(f"Error fetching coin ID for {ticker}: {e}")
            return None

    def fetch_price(self, coin_id):
        """Fetch price for a single coin"""
        try:
            time.sleep(max(0, self.min_api_delay - (time.time() - self.last_api_call)))
            self.last_api_call = time.time()

            url = f'https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true'
            response = requests.get(url, timeout=10)

            if response.status_code == 429:
                print(f'⚠️  Rate limited by CoinGecko API for coin: {coin_id}')
                print('   Please wait a minute before trying again.')
                return None

            data = response.json()

            if coin_id in data:
                return {
                    'price': data[coin_id]['usd'],
                    'change24h': data[coin_id].get('usd_24h_change', 0)
                }

            return None
        except Exception as e:
            print(f"Error fetching price for {coin_id}: {e}")
            return None

    def fetch_pair_price(self, base_coin_id, quote_coin_id):
        """Fetch price for a trading pair"""
        try:
            time.sleep(max(0, self.min_api_delay - (time.time() - self.last_api_call)))
            self.last_api_call = time.time()

            url = f'https://api.coingecko.com/api/v3/simple/price?ids={base_coin_id},{quote_coin_id}&vs_currencies=usd&include_24hr_change=true'
            response = requests.get(url, timeout=10)

            if response.status_code == 429:
                print(f'⚠️  Rate limited by CoinGecko API for pair: {base_coin_id}/{quote_coin_id}')
                print('   Please wait a minute before trying again.')
                return None

            data = response.json()

            if base_coin_id in data and quote_coin_id in data:
                base_price = data[base_coin_id]['usd']
                quote_price = data[quote_coin_id]['usd']
                pair_price = base_price / quote_price

                base_change = data[base_coin_id].get('usd_24h_change', 0)
                quote_change = data[quote_coin_id].get('usd_24h_change', 0)
                pair_change = base_change - quote_change

                return {
                    'price': pair_price,
                    'change24h': pair_change
                }

            return None
        except Exception as e:
            print(f"Error fetching pair price: {e}")
            return None

    def add_asset(self, pair_string):
        """Add a new trading pair to monitor"""
        parsed = self.parse_trading_pair(pair_string)

        if not parsed:
            return {'success': False, 'message': 'Invalid pair format. Try: BTCUSDT, ETHBTC, etc.'}

        base = parsed['base']
        quote = parsed['quote']
        pair = parsed['pair']

        if pair in self.assets:
            return {'success': False, 'message': 'Pair already added'}

        # Fetch base asset info
        base_coin_info = self.fetch_coin_id(base)
        if not base_coin_info:
            return {'success': False, 'message': f'Could not fetch "{base}". Either invalid symbol or API rate limited. Wait 1-2 minutes and try again.'}

        # Handle quote asset
        quote_coin_info = None
        price_data = None

        if self.is_stablecoin(quote):
            # For stablecoins, just use base price in USD
            price_data = self.fetch_price(base_coin_info['id'])
        else:
            # For non-stablecoin pairs, fetch both assets
            quote_coin_info = self.fetch_coin_id(quote)
            if not quote_coin_info:
                return {'success': False, 'message': f'Could not fetch "{quote}". Either invalid symbol or API rate limited. Wait 1-2 minutes and try again.'}

            price_data = self.fetch_pair_price(base_coin_info['id'], quote_coin_info['id'])

        if not price_data:
            return {'success': False, 'message': 'Could not fetch price data. API may be rate limited. Wait 1-2 minutes and try again.'}

        # Create asset
        asset = {
            'ticker': pair,
            'base': base,
            'quote': quote,
            'baseCoinId': base_coin_info['id'],
            'quoteCoinId': quote_coin_info['id'] if quote_coin_info else None,
            'name': f"{base_coin_info['name']}/{quote}",
            'baseName': base_coin_info['name'],
            'price': price_data['price'],
            'change24h': price_data['change24h'],
            'maxPrice': price_data['price'],
            'minPrice': price_data['price'],
            'lastUpdate': time.time()
        }

        with self.lock:
            self.assets[pair] = asset
            self.price_history[pair] = [{'price': price_data['price'], 'timestamp': time.time()}]
            self.save_data()

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

                # Start a timer to reset it
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
                price_data = None

                if self.is_stablecoin(asset['quote']):
                    price_data = self.fetch_price(asset['baseCoinId'])
                else:
                    price_data = self.fetch_pair_price(asset['baseCoinId'], asset['quoteCoinId'])

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
                        message = f"{asset['name']} ({ticker}) reached target price!"

                elif alarm['type'] == 'extreme':
                    should_trigger, direction = self.check_extreme_alarm(alarm, asset)
                    if should_trigger:
                        message = f"{asset['name']} ({ticker}) hit extreme price level!"

                elif alarm['type'] == 'timeframe':
                    should_trigger, direction = self.check_timeframe_alarm(alarm, asset)
                    if should_trigger:
                        message = f"{asset['name']} ({ticker}) hit timeframe target!"

                if should_trigger:
                    # Handle "since_start" alarms differently
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
            # Calculate timeframe in seconds
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

        # Find relevant history
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
        print("Monitoring started")
        while self.monitoring:
            try:
                # Update prices
                self.update_all_prices()

                # Check alarms
                triggered = self.check_alarms()

                # Notify via callback
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

            # Wait 15 seconds before next update
            time.sleep(15)

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
