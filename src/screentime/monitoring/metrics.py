"""Muestreo asíncrono y ligero de métricas con throttling configurable."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from queue import Full, Queue
from typing import Any, Deque, List, Optional, Protocol

from screentime.monitoring.providers import GpuReading, MemoryReading


class CpuRamProvider(Protocol):
    def sample(self) -> tuple[float, MemoryReading]: ...


class GpuProvider(Protocol):
    def sample(self) -> Optional[GpuReading]: ...


@dataclass(frozen=True)
class MetricSnapshot:
    """Foto inmutable de un instante de métricas."""

    ts: float
    cpu: float
    ram: float
    ram_used: int
    ram_total: int
    gpu: Optional[float] = None
    gpu_mem_used: Optional[int] = None
    gpu_mem_total: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MetricsSampler:
    """Hilo daemon que muestrea métricas y notifica a suscriptores.

    - Throttling: espera `interval` segundos entre muestras sin bloquear.
    - No invasivo: una sola lectura por ciclo y errores aislados.
    - Suscripción: colas acotadas; si el cliente va lento se descartan muestras.
    """

    def __init__(
        self,
        interval: float = 2.0,
        history: int = 120,
        gpu_interval: float = 5.0,
        cpu_ram: Optional[CpuRamProvider] = None,
        gpu: Optional[GpuProvider] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.interval = max(0.5, float(interval))
        self.gpu_interval = max(1.0, float(gpu_interval))
        self._cpu_ram = cpu_ram
        self._gpu = gpu
        self._logger = logger
        self._last_gpu: Optional[GpuReading] = None
        self._last_gpu_ts = -1e9
        self._history: Deque[MetricSnapshot] = deque(maxlen=max(10, int(history)))
        self._latest: Optional[MetricSnapshot] = None
        self._lock = threading.Lock()
        self._subs_lock = threading.Lock()
        self._subscribers: List[Queue] = []
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_error = 0.0

        if self._cpu_ram is None:
            from screentime.monitoring.providers import CpuRamProvider as _CpuRam

            self._cpu_ram = _CpuRam()
        if self._gpu is None:
            from screentime.monitoring.providers import GpuProvider as _Gpu

            self._gpu = _Gpu()

    # ─── Ciclo de vida ───────────────────────────────────────────────────

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="metrics-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread and thread.is_alive():
            thread.join(timeout=2.0)

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ─── Lectura / suscripción ───────────────────────────────────────────

    def latest(self) -> Optional[MetricSnapshot]:
        with self._lock:
            return self._latest

    def history(self) -> List[MetricSnapshot]:
        with self._lock:
            return list(self._history)

    def subscribe(self, maxsize: int = 120) -> Queue:
        queue: Queue = Queue(maxsize=maxsize)
        with self._subs_lock:
            self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: Queue) -> None:
        with self._subs_lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)

    # ─── Interno ─────────────────────────────────────────────────────────

    def _run(self) -> None:
        while not self._stop.is_set():
            self.sample_once()
            self._stop.wait(self.interval)

    def sample_once(self) -> Optional[MetricSnapshot]:
        try:
            cpu, mem = self._cpu_ram.sample()
        except Exception as exc:  # proveedor no disponible: se omite el ciclo
            self._log_error(exc)
            return None

        now = time.monotonic()
        if now - self._last_gpu_ts >= self.gpu_interval:
            self._last_gpu_ts = now
            try:
                self._last_gpu = self._gpu.sample()
            except Exception as exc:
                self._log_error(exc)
        gpu_reading = self._last_gpu

        snapshot = MetricSnapshot(
            ts=time.time(),
            cpu=round(cpu, 1),
            ram=round(mem.percent, 1),
            ram_used=mem.used,
            ram_total=mem.total,
            gpu=round(gpu_reading.percent, 1) if gpu_reading else None,
            gpu_mem_used=gpu_reading.mem_used if gpu_reading else None,
            gpu_mem_total=gpu_reading.mem_total if gpu_reading else None,
        )
        with self._lock:
            self._latest = snapshot
            self._history.append(snapshot)

        with self._subs_lock:
            subscribers = list(self._subscribers)
        payload = snapshot.to_dict()
        for queue in subscribers:
            try:
                queue.put_nowait(payload)
            except Full:
                pass
        return snapshot

    def _log_error(self, exc: Exception) -> None:
        now = time.monotonic()
        if now - self._last_error >= 60.0:
            self._last_error = now
            if self._logger:
                self._logger.warning("Fallo muestreando metricas: %s", exc)
