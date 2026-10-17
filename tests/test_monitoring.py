"""Tests del monitoreo de recursos y utilidades de configuración."""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from screentime.config_env import get_bool, get_float, get_int
from screentime.monitoring.metrics import MetricsSampler
from screentime.monitoring.providers import GpuProvider, GpuReading, MemoryReading


class FakeCpuRam:
    def sample(self):
        return 42.0, MemoryReading(percent=55.5, used=2 * 1024**3, total=8 * 1024**3)


class FakeGpu:
    def __init__(self, reading):
        self.reading = reading

    def sample(self):
        return self.reading


class ConfigEnvTests(unittest.TestCase):
    def test_int_default_and_clamp(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("X_TEST", None)
            self.assertEqual(get_int("X_TEST", 5), 5)
        with mock.patch.dict(os.environ, {"X_TEST": "999"}, clear=False):
            self.assertEqual(get_int("X_TEST", 5, 10, 100), 100)
        with mock.patch.dict(os.environ, {"X_TEST": "abc"}, clear=False):
            self.assertEqual(get_int("X_TEST", 7), 7)

    def test_float_and_bool(self):
        with mock.patch.dict(os.environ, {"X_F": "1.5", "X_B": "yes"}, clear=False):
            self.assertEqual(get_float("X_F", 0.0, 1.0, 2.0), 1.5)
            self.assertTrue(get_bool("X_B"))
        with mock.patch.dict(os.environ, {"X_B": "off"}, clear=False):
            self.assertFalse(get_bool("X_B", True))


class SamplerTests(unittest.TestCase):
    def _sampler(self, gpu=None):
        return MetricsSampler(interval=0.5, history=10, cpu_ram=FakeCpuRam(), gpu=FakeGpu(gpu))

    def test_sample_once(self):
        sampler = self._sampler(GpuReading(percent=10.0, mem_used=100, mem_total=1000))
        snap = sampler.sample_once()
        self.assertIsNotNone(snap)
        self.assertEqual(snap.cpu, 42.0)
        self.assertEqual(snap.ram, 55.5)
        self.assertEqual(snap.gpu, 10.0)
        self.assertEqual(snap.gpu_mem_total, 1000)

    def test_gpu_absent_is_none(self):
        sampler = self._sampler(None)
        snap = sampler.sample_once()
        self.assertIsNone(snap.gpu)
        self.assertIsNone(snap.gpu_mem_used)

    def test_history_is_bounded(self):
        sampler = self._sampler(None)
        for _ in range(15):
            sampler.sample_once()
        self.assertEqual(len(sampler.history()), 10)
        self.assertIsNotNone(sampler.latest())

    def test_subscriber_receives_payload(self):
        sampler = self._sampler(None)
        queue = sampler.subscribe()
        try:
            sampler.sample_once()
            payload = queue.get_nowait()
            self.assertEqual(payload["cpu"], 42.0)
        finally:
            sampler.unsubscribe(queue)

    def test_gpu_sampling_is_throttled(self):
        class CountingGpu:
            def __init__(self):
                self.calls = 0

            def sample(self):
                self.calls += 1
                return GpuReading(percent=1.0, mem_used=0, mem_total=0)

        gpu = CountingGpu()
        sampler = MetricsSampler(
            interval=0.5, history=10, gpu_interval=100.0, cpu_ram=FakeCpuRam(), gpu=gpu,
        )
        for _ in range(3):
            sampler.sample_once()
        self.assertEqual(gpu.calls, 1)

    def test_provider_error_does_not_raise(self):
        class Broken:
            def sample(self):
                raise RuntimeError("boom")

        sampler = MetricsSampler(interval=0.5, history=10, cpu_ram=Broken(), gpu=FakeGpu(None))
        self.assertIsNone(sampler.sample_once())


class GpuDetectionTests(unittest.TestCase):
    def test_unavailable_without_nvidia_or_pdh(self):
        with mock.patch("screentime.monitoring.providers.shutil.which", return_value=None), \
                mock.patch("screentime.monitoring.providers._PdhGpuCounter") as pdh_cls:
            pdh_cls.return_value.available = False
            provider = GpuProvider()
        self.assertFalse(provider.available)
        self.assertIsNone(provider.sample())

    @unittest.skipUnless(sys.platform == "win32", "solo Windows")
    def test_windows_pdh_detects_gpu(self):
        with mock.patch("screentime.monitoring.providers.shutil.which", return_value=None):
            provider = GpuProvider()
        self.assertTrue(provider.available)
        reading = provider.sample()
        self.assertTrue(reading is None or 0.0 <= reading.percent <= 100.0)


if __name__ == "__main__":
    unittest.main()
