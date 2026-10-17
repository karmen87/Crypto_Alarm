import unittest

from crypto_alarm import rules
from crypto_alarm.models import Asset, ExtremeAlarm, TargetAlarm, TimeframeAlarm


class ValidationTests(unittest.TestCase):
    def test_positive_float_rejects_bad_values(self):
        for bad in ("nan", "inf", "-1", "0", 0, None, "abc"):
            with self.assertRaises(ValueError):
                rules.positive_float(bad, "x")
        self.assertEqual(rules.positive_float("1.5", "x"), 1.5)

    def test_choice(self):
        self.assertEqual(rules.choice("up", rules.DIRECTIONS, "direction"), "up")
        with self.assertRaises(ValueError):
            rules.choice("sideways", rules.DIRECTIONS, "direction")

    def test_time_value(self):
        self.assertIsNone(rules.time_value(None, "since_start"))
        self.assertEqual(rules.time_value("15", "minutes"), 15)
        for bad in ("0", "-3", "abc", None):
            with self.assertRaises(ValueError):
                rules.time_value(bad, "hours")
        with self.assertRaises(ValueError):
            rules.time_value("8", "days")


class TargetTests(unittest.TestCase):
    def alarm(self, direction, prev):
        return TargetAlarm(
            id="a", ticker="X", target_price=100.0, direction=direction, prev_price=prev
        )

    def test_crossing_up_and_down(self):
        self.assertEqual(rules.check_target(self.alarm("up", 99), 100), (True, "up"))
        self.assertEqual(rules.check_target(self.alarm("down", 101), 100), (True, "down"))
        self.assertEqual(rules.check_target(self.alarm("any", 99), 101), (True, "up"))
        self.assertEqual(rules.check_target(self.alarm("any", 101), 99), (True, "down"))

    def test_wrong_direction_or_no_cross(self):
        self.assertEqual(rules.check_target(self.alarm("up", 101), 99), (False, None))
        self.assertEqual(rules.check_target(self.alarm("down", 99), 101), (False, None))
        self.assertEqual(rules.check_target(self.alarm("up", 90), 95), (False, None))

    def test_first_check_fires_when_already_beyond_target(self):
        self.assertEqual(rules.check_target(self.alarm("up", None), 105), (True, "up"))
        self.assertEqual(rules.check_target(self.alarm("down", None), 95), (True, "down"))
        self.assertEqual(rules.check_target(self.alarm("up", None), 95), (False, None))
        self.assertEqual(rules.check_target(self.alarm("any", None), 100.05), (True, "up"))
        self.assertEqual(rules.check_target(self.alarm("any", None), 110), (False, None))


class ExtremeTests(unittest.TestCase):
    def test_down_from_max_and_up_from_min(self):
        asset = Asset(
            ticker="X", base="X", quote="USDT", price=90.0, max_price=100.0, min_price=80.0
        )

        def alarm(kind, pct):
            return ExtremeAlarm(id="a", ticker="X", extreme_type=kind, percentage=pct)

        self.assertEqual(rules.check_extreme(alarm("max", 10), asset), (True, "down"))
        self.assertEqual(rules.check_extreme(alarm("max", 11), asset), (False, None))
        self.assertEqual(rules.check_extreme(alarm("min", 12), asset), (True, "up"))
        self.assertEqual(rules.check_extreme(alarm("min", 13), asset), (False, None))


class TimeframeTests(unittest.TestCase):
    def setUp(self):
        self.now = 10_000.0
        # 100 an hour ago, 100 half an hour ago, 110 now
        self.history = [(self.now - 3600, 100.0), (self.now - 1800, 100.0), (self.now, 110.0)]

    def alarm(self, direction="up", pct=5, unit="hours", value=1, start_price=None):
        return TimeframeAlarm(
            id="a",
            ticker="X",
            percentage=pct,
            direction=direction,
            time_unit=unit,
            time_value=value,
            start_price=start_price,
        )

    def test_window_uses_price_one_full_window_ago(self):
        result = rules.check_timeframe(self.alarm(), 110.0, self.history, self.now)
        self.assertEqual(result, (True, "up", 100.0))

    def test_silent_until_history_reaches_back_a_full_window(self):
        hit, _, start = rules.check_timeframe(self.alarm(value=2), 110.0, self.history, self.now)
        self.assertFalse(hit)
        self.assertIsNone(start)

    def test_direction_filter(self):
        self.assertFalse(
            rules.check_timeframe(self.alarm("down"), 110.0, self.history, self.now)[0]
        )
        self.assertTrue(rules.check_timeframe(self.alarm("any"), 110.0, self.history, self.now)[0])
        self.assertTrue(rules.check_timeframe(self.alarm("down"), 94.0, self.history, self.now)[0])

    def test_since_start_uses_stored_start_price(self):
        alarm = self.alarm(unit="since_start", value=None, start_price=100.0)
        self.assertEqual(rules.check_timeframe(alarm, 106.0, [], self.now), (True, "up", 100.0))
        alarm.start_price = None
        self.assertFalse(rules.check_timeframe(alarm, 106.0, [], self.now)[0])


if __name__ == "__main__":
    unittest.main()
