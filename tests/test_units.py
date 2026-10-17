"""Tests unitarios basicos de Screen Time Notifier."""

import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import screentime.logger as logger_module
from screentime.logger import UsageLogger
from screentime.shutdown import COUNTDOWN, FIXED_TIME, ShutdownScheduler, format_remaining
from screentime.theme import unpack_touchpad_delta as _unpack_touchpad_delta


class ScrollDecodeTests(unittest.TestCase):
    def test_vertical_down_wrapped(self):
        # -40 empaquetado en 16 bits: 0xFFD8
        self.assertEqual(_unpack_touchpad_delta(65496), (0, -40))

    def test_vertical_up(self):
        self.assertEqual(_unpack_touchpad_delta(40), (0, 40))

    def test_both_axes(self):
        packed = ((-40) & 0xFFFF) | (25 << 16)
        self.assertEqual(_unpack_touchpad_delta(packed), (25, -40))

    def test_zero(self):
        self.assertEqual(_unpack_touchpad_delta(0), (0, 0))


class LoggerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._old_data = logger_module.DATA_DIR
        self._old_file = logger_module.HISTORY_FILE
        logger_module.DATA_DIR = self.tmp
        logger_module.HISTORY_FILE = os.path.join(self.tmp, "history.json")

    def tearDown(self):
        logger_module.DATA_DIR = self._old_data
        logger_module.HISTORY_FILE = self._old_file

    def test_legacy_history_without_total_is_normalized(self):
        with open(logger_module.HISTORY_FILE, "w", encoding="utf-8") as f:
            f.write('{"daily_sessions": {}}')
        log = UsageLogger()
        data = log.get_history()
        self.assertIn("total_usage_seconds", data)
        log.save_session()  # antes lanzaba KeyError
        self.assertGreaterEqual(log.get_history()["total_usage_seconds"], 0)

    def test_corrupt_history_falls_back(self):
        with open(logger_module.HISTORY_FILE, "w", encoding="utf-8") as f:
            f.write("{no es json valido")
        log = UsageLogger()
        self.assertEqual(log.get_history()["daily_sessions"], {})
        self.assertEqual(log.get_history()["total_usage_seconds"], 0)

    def test_elapsed_is_non_negative(self):
        log = UsageLogger()
        self.assertGreaterEqual(log.get_elapsed_seconds(), 0)

    def test_retention_prunes_old_days(self):
        old = (date.today() - timedelta(days=10)).isoformat()
        with open(logger_module.HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"daily_sessions": {old: {"sessions": [], "total_seconds": 60}},
                       "total_usage_seconds": 60}, f)
        log = UsageLogger(retention_days=5)
        log.save_session()
        data = log.get_history()
        self.assertNotIn(old, data["daily_sessions"])
        self.assertIn(date.today().isoformat(), data["daily_sessions"])

    def test_format_seconds(self):
        log = UsageLogger()
        self.assertEqual(log.format_seconds(0), "0m")
        self.assertEqual(log.format_seconds(90), "1m")
        self.assertEqual(log.format_seconds(3660), "1h 01m")


class ShutdownTests(unittest.TestCase):
    def test_format_remaining(self):
        self.assertEqual(format_remaining(0), "0s")
        self.assertEqual(format_remaining(8), "8s")
        self.assertEqual(format_remaining(50), "50s")
        self.assertEqual(format_remaining(610), "10m 10s")
        self.assertEqual(format_remaining(3661), "1h 01m 01s")

    def test_countdown_target_is_near_now_plus_minutes(self):
        s = ShutdownScheduler()
        try:
            s.configure(enabled=True, mode=COUNTDOWN, minutes=60)
            self.assertTrue(s.is_enabled)
            remaining = s.seconds_remaining()
            self.assertIsNotNone(remaining)
            self.assertGreater(remaining, 3500)
            self.assertLessEqual(remaining, 3600)
        finally:
            s.cancel()
            s.stop()

    def test_fixed_time_status_contains_hour(self):
        s = ShutdownScheduler()
        try:
            s.configure(enabled=True, mode=FIXED_TIME, time_str="23:59", warn_minutes=5)
            self.assertTrue(s.is_enabled)
            self.assertIsNotNone(s.target)
            self.assertIn("23:59", s.status_text())
        finally:
            s.cancel()
            s.stop()

    def test_postpone_requires_schedule(self):
        s = ShutdownScheduler()
        self.assertFalse(s.postpone(10))

    def test_cancel_disables_and_clears(self):
        s = ShutdownScheduler()
        s.configure(enabled=True, mode=COUNTDOWN, minutes=30)
        s.cancel()
        s.stop()
        self.assertFalse(s.is_enabled)
        self.assertIsNone(s.target)


if __name__ == "__main__":
    unittest.main()
