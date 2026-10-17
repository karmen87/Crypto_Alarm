import dataclasses
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from crypto_alarm.binance import InvalidSymbol, RateLimited
from crypto_alarm.monitor import Monitor
from crypto_alarm.settings import Settings
from crypto_alarm.store import JsonStore


def tick(price):
    return {"price": price, "change24h": 1.0, "high24h": price, "low24h": price, "volume": 1.0}


class FakeClient:
    def __init__(self):
        self.error = None

    def get_symbol_info(self, symbol):
        if self.error:
            raise self.error
        if symbol == "NOPEUSDT":
            raise InvalidSymbol("Invalid symbol")
        return {"base": symbol[:-4], "quote": symbol[-4:]}

    def get_tickers(self, symbols):
        return {s: tick(100.0) for s in symbols}

    def get_history(self, symbol, retention_days=8):
        return [(time.time() - 3600 + i * 300, 100.0) for i in range(5)]


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "data.json"
        self.settings = dataclasses.replace(Settings(), data_file=self.path)
        self.client = FakeClient()
        self.monitor = self.make_monitor(self.client)

    def tearDown(self):
        self.tmp.cleanup()

    def make_monitor(self, client):
        return Monitor(self.settings, client, JsonStore(self.path))

    def add_pair(self, pair="BTCUSDT"):
        return self.monitor.add_asset(pair)

    def test_add_asset_uses_exchange_info_and_rejects_bad_input(self):
        asset = self.add_pair("BTCUSDT")
        self.assertEqual((asset["base"], asset["quote"]), ("BTC", "USDT"))
        with self.assertRaises(ValueError):
            self.monitor.add_asset("btc/usdt&x=1")
        with self.assertRaises(ValueError):
            self.monitor.add_asset("NOPEUSDT")
        with self.assertRaisesRegex(ValueError, "already"):
            self.monitor.add_asset("BTCUSDT")

    def test_rate_limit_is_reported_not_called_not_found(self):
        self.client.error = RateLimited(30)
        with self.assertRaises(ValueError) as ctx:
            self.monitor.add_asset("ETHUSDT")
        self.assertIn("rate limit", str(ctx.exception))
        self.assertNotIn("not found", str(ctx.exception))

    def test_alarm_validation(self):
        self.add_pair()
        with self.assertRaises(ValueError):
            self.monitor.add_target_alarm("BTCUSDT", "nan", "up")
        with self.assertRaises(ValueError):
            self.monitor.add_target_alarm("BTCUSDT", 0, "up")
        with self.assertRaises(ValueError):
            self.monitor.add_target_alarm("ETHUSDT", 100, "up")  # unknown pair
        with self.assertRaises(ValueError):
            self.monitor.add_extreme_alarm("BTCUSDT", 5, "middle")
        with self.assertRaises(ValueError):
            self.monitor.add_timeframe_alarm("BTCUSDT", 5, "up", "x", "hours")

    def test_target_alarm_fires_once_on_crossing(self):
        self.add_pair()
        self.monitor.add_target_alarm("BTCUSDT", 105, "up")
        now = time.time()
        self.monitor.on_tick("BTCUSDT", tick(100.0), now)
        self.assertEqual(self.monitor.check_alarms(now), [])
        self.monitor.on_tick("BTCUSDT", tick(106.0), now + 1)
        events = self.monitor.check_alarms(now + 1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].direction, "up")
        self.assertEqual(self.monitor.check_alarms(now + 2), [])  # already triggered
        self.assertEqual(len(self.monitor.get_pending_events()), 1)  # unacknowledged

        self.monitor.acknowledge_alarm(events[0].alarm.id)
        self.assertEqual(self.monitor.get_pending_events(), [])

    def test_restart_cooldown_does_not_refire_until_new_crossing(self):
        self.add_pair()
        alarm = self.monitor.add_target_alarm("BTCUSDT", 105, "up")
        now = time.time()
        self.monitor.on_tick("BTCUSDT", tick(106.0), now)
        self.assertEqual(len(self.monitor.check_alarms(now)), 1)

        self.monitor.restart_alarm(alarm["id"])
        until = self.monitor.alarms[alarm["id"]].reset_until
        self.assertGreater(until, 0)
        self.monitor.on_tick("BTCUSDT", tick(107.0), now + 5)
        self.assertEqual(self.monitor.check_alarms(now + 5), [])  # cooling down

        late = until + 1  # re-armed from the current price
        self.monitor.on_tick("BTCUSDT", tick(107.0), late)
        self.assertEqual(self.monitor.check_alarms(late), [])
        self.monitor.on_tick("BTCUSDT", tick(100.0), late + 1)
        self.monitor.check_alarms(late + 1)
        self.monitor.on_tick("BTCUSDT", tick(106.0), late + 2)
        self.assertEqual(len(self.monitor.check_alarms(late + 2)), 1)

    def test_restart_is_target_only(self):
        self.add_pair()
        alarm = self.monitor.add_extreme_alarm("BTCUSDT", 5, "max")
        with self.assertRaises(ValueError):
            self.monitor.restart_alarm(alarm["id"])

    def test_stale_prices_do_not_trigger(self):
        self.add_pair()
        self.monitor.add_target_alarm("BTCUSDT", 90, "up")
        last = self.monitor.assets["BTCUSDT"].last_update
        self.assertEqual(self.monitor.check_alarms(last + self.settings.max_price_age + 1), [])
        stale = self.monitor.get_state()["assets"]["BTCUSDT"]["stale"]
        self.assertFalse(stale)  # computed against the real clock: just added, so fresh

    def test_since_start_alarm_repeats(self):
        self.add_pair()
        self.monitor.add_timeframe_alarm("BTCUSDT", 5, "up", None, "since_start")
        now = time.time()
        self.monitor.on_tick("BTCUSDT", tick(106.0), now)
        self.assertEqual(len(self.monitor.check_alarms(now)), 1)
        self.monitor.on_tick("BTCUSDT", tick(107.0), now + 1)
        self.assertEqual(self.monitor.check_alarms(now + 1), [])  # start price reset to 106
        self.monitor.on_tick("BTCUSDT", tick(112.0), now + 2)
        self.assertEqual(len(self.monitor.check_alarms(now + 2)), 1)

    def test_extreme_alarm_tracks_max_and_can_be_reset(self):
        self.add_pair()
        self.monitor.add_extreme_alarm("BTCUSDT", 10, "max")
        now = time.time()
        self.monitor.on_tick("BTCUSDT", tick(120.0), now)
        self.assertEqual(self.monitor.check_alarms(now), [])
        self.monitor.assets["BTCUSDT"].max_price = 150.0  # an old peak
        self.monitor.reset_extremes("BTCUSDT")  # restart tracking from the current price (120)
        self.assertEqual(self.monitor.assets["BTCUSDT"].max_price, 120.0)
        self.monitor.on_tick("BTCUSDT", tick(115.0), now + 1)
        self.assertEqual(self.monitor.check_alarms(now + 1), [])  # only 4% below the new max

    def test_history_sampling_and_persistence_round_trip(self):
        self.add_pair()
        now = time.time() + 100  # after the sample stored by add_asset
        before = len(self.monitor.history["BTCUSDT"])
        self.monitor.on_tick("BTCUSDT", tick(101.0), now)
        self.monitor.on_tick("BTCUSDT", tick(102.0), now + 1)  # inside the spacing: not stored
        self.assertEqual(len(self.monitor.history["BTCUSDT"]), before + 1)

        self.monitor.add_target_alarm("BTCUSDT", 150, "up")
        reloaded = self.make_monitor(FakeClient())
        self.assertEqual(set(reloaded.assets), {"BTCUSDT"})
        self.assertEqual(len(reloaded.alarms), 1)
        self.assertFalse(os.path.exists(str(self.path) + ".tmp"))
        self.assertNotIn("price_history", json.loads(self.path.read_text(encoding="utf-8")))

    def test_corrupt_data_file_is_preserved(self):
        self.path.write_text("{not json")
        monitor = self.make_monitor(FakeClient())
        self.assertEqual(monitor.assets, {})
        self.assertTrue(os.path.exists(str(self.path) + ".corrupt"))

    def test_remove_asset_removes_alarms(self):
        self.add_pair()
        self.monitor.add_target_alarm("BTCUSDT", 150, "up")
        self.monitor.remove_asset("BTCUSDT")
        self.assertEqual(
            (self.monitor.assets, self.monitor.alarms, self.monitor.history), ({}, {}, {})
        )


if __name__ == "__main__":
    unittest.main()
