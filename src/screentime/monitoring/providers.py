"""Proveedores de métricas del sistema (CPU/RAM y GPU)."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

import psutil

_CREATE_NO_WINDOW = 0x08000000
_NVIDIA_QUERY = "--query-gpu=utilization.gpu,memory.used,memory.total"
_NVIDIA_FORMAT = "--format=csv,noheader,nounits"
_PDH_FMT_DOUBLE = 0x00000200
_GPU_COUNTER = r"\GPU Engine(*)\Utilization Percentage"


@dataclass(frozen=True)
class MemoryReading:
    percent: float
    used: int
    total: int


@dataclass(frozen=True)
class GpuReading:
    percent: float
    mem_used: int
    mem_total: int


class CpuRamProvider:
    """Lecturas no bloqueantes de CPU y RAM vía psutil."""

    def __init__(self) -> None:
        psutil.cpu_percent(interval=None)  # primera lectura descartada

    def sample(self) -> tuple[float, MemoryReading]:
        cpu = float(psutil.cpu_percent(interval=None))
        vm = psutil.virtual_memory()
        return cpu, MemoryReading(percent=float(vm.percent), used=int(vm.used), total=int(vm.total))


class _PdhCounterValue(ctypes.Structure):
    _fields_ = [("CStatus", wintypes.DWORD), ("doubleValue", ctypes.c_double)]


class _PdhItem(ctypes.Structure):
    _fields_ = [("szName", wintypes.LPWSTR), ("FmtValue", _PdhCounterValue)]


class _PdhGpuCounter:
    """GPU utilization vía PDH (contadores de rendimiento de Windows).

    Detecta cualquier GPU (AMD/Intel/NVIDIA) mediante el contador
    ``GPU Engine``. No usa subprocess ni dependencias externas.
    """

    def __init__(self) -> None:
        self._available = False
        self._pdh = None
        self._query = None
        self._counter = None
        try:
            pdh = ctypes.WinDLL("pdh", use_last_error=True)
            pdh.PdhOpenQueryW.argtypes = [wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]
            pdh.PdhOpenQueryW.restype = wintypes.LONG
            pdh.PdhAddEnglishCounterW.argtypes = [
                ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p),
            ]
            pdh.PdhAddEnglishCounterW.restype = wintypes.LONG
            pdh.PdhCollectQueryData.argtypes = [ctypes.c_void_p]
            pdh.PdhCollectQueryData.restype = wintypes.LONG
            pdh.PdhGetFormattedCounterArrayW.argtypes = [
                ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(_PdhItem),
            ]
            pdh.PdhGetFormattedCounterArrayW.restype = wintypes.LONG
            pdh.PdhCloseQuery.argtypes = [ctypes.c_void_p]
            pdh.PdhCloseQuery.restype = wintypes.LONG

            query = ctypes.c_void_p()
            if pdh.PdhOpenQueryW(None, 0, ctypes.byref(query)) != 0:
                return
            counter = ctypes.c_void_p()
            if pdh.PdhAddEnglishCounterW(query, _GPU_COUNTER, 0, ctypes.byref(counter)) != 0:
                pdh.PdhCloseQuery(query)
                return
            pdh.PdhCollectQueryData(query)  # priming: la 1.ª lectura de tasa no es válida
            self._pdh, self._query, self._counter = pdh, query, counter
            self._available = True
        except Exception:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def read(self) -> Optional[float]:
        if not self._available:
            return None
        try:
            if self._pdh.PdhCollectQueryData(self._query) != 0:
                return None
            size = wintypes.DWORD(0)
            count = wintypes.DWORD(0)
            self._pdh.PdhGetFormattedCounterArrayW(
                self._counter, _PDH_FMT_DOUBLE, ctypes.byref(size), ctypes.byref(count), None,
            )
            if not count.value or not size.value:
                return None
            buffer = ctypes.create_string_buffer(size.value)
            items = ctypes.cast(buffer, ctypes.POINTER(_PdhItem))
            if self._pdh.PdhGetFormattedCounterArrayW(
                self._counter, _PDH_FMT_DOUBLE, ctypes.byref(size), ctypes.byref(count), items,
            ) != 0:
                return None
            engines: dict[str, float] = {}
            for i in range(count.value):
                item = items[i]
                if item.FmtValue.CStatus > 1:  # solo datos válidos
                    continue
                name = item.szName or ""
                key = name.rsplit("_engtype_", 1)[-1] if "_engtype_" in name else "gpu"
                engines[key] = engines.get(key, 0.0) + max(0.0, float(item.FmtValue.doubleValue))
            if not engines:
                return None
            return min(100.0, max(engines.values()))
        except Exception:
            return None


class GpuProvider:
    """GPU: NVIDIA vía nvidia-smi; cualquier otra vía PDH. Opcional."""

    def __init__(self) -> None:
        self._cmd = shutil.which("nvidia-smi")
        self._pdh: Optional[_PdhGpuCounter] = None
        self._mode: Optional[str] = None
        if self._cmd:
            self._mode = "nvidia"
        elif sys.platform == "win32":
            pdh = _PdhGpuCounter()
            if pdh.available:
                self._pdh = pdh
                self._mode = "pdh"

    @property
    def available(self) -> bool:
        return self._mode is not None

    def sample(self) -> Optional[GpuReading]:
        if self._mode == "pdh" and self._pdh is not None:
            value = self._pdh.read()
            if value is None:
                return None
            return GpuReading(percent=value, mem_used=0, mem_total=0)
        if self._mode == "nvidia":
            return self._read_nvidia()
        return None

    def _read_nvidia(self) -> Optional[GpuReading]:
        if not self._cmd:
            return None
        try:
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = _CREATE_NO_WINDOW
            result = subprocess.run(
                [self._cmd, _NVIDIA_QUERY, _NVIDIA_FORMAT],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
                **kwargs,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return None
            first = result.stdout.strip().splitlines()[0]
            parts = [part.strip() for part in first.split(",")]
            if len(parts) < 3:
                return None
            return GpuReading(
                percent=float(parts[0]),
                mem_used=int(float(parts[1])),
                mem_total=int(float(parts[2])),
            )
        except (OSError, subprocess.SubprocessError, ValueError, IndexError):
            return None
