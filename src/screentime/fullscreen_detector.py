"""Detección de modo juego / pantalla completa."""

import ctypes
import ctypes.wintypes
import threading
import time
from typing import Callable, Optional

# ctypes.wintypes no define MONITORINFO, hay que declararla a mano.
_MONITOR_DEFAULTTONEAREST = 2
_IGNORED_WINDOW_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("rcMonitor", ctypes.wintypes.RECT),
        ("rcWork", ctypes.wintypes.RECT),
        ("dwFlags", ctypes.wintypes.DWORD),
    ]


_user32 = None


def _get_user32():
    """Devuelve user32 con las firmas configuradas una sola vez (cacheado)."""
    global _user32
    if _user32 is None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetForegroundWindow.restype = ctypes.wintypes.HWND
        user32.GetClassNameW.argtypes = [
            ctypes.wintypes.HWND, ctypes.wintypes.LPWSTR, ctypes.c_int,
        ]
        user32.GetWindowRect.argtypes = [
            ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.RECT),
        ]
        user32.MonitorFromWindow.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.DWORD]
        user32.MonitorFromWindow.restype = ctypes.wintypes.HMONITOR
        user32.GetMonitorInfoW.argtypes = [ctypes.wintypes.HMONITOR, ctypes.POINTER(_MONITORINFO)]
        _user32 = user32
    return _user32


class FullscreenDetector:
    """Detecta si una aplicación está en pantalla completa."""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callback_enter: Optional[Callable] = None
        self._callback_exit: Optional[Callable] = None
        self._is_fullscreen = False
        self._check_interval = 2

    def set_callbacks(self, on_enter: Callable = None, on_exit: Callable = None):
        self._callback_enter = on_enter
        self._callback_exit = on_exit

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    @property
    def is_fullscreen(self) -> bool:
        return self._is_fullscreen

    def _loop(self):
        while self._running:
            try:
                detected = self._check_fullscreen()
                if detected and not self._is_fullscreen:
                    self._is_fullscreen = True
                    if self._callback_enter:
                        self._callback_enter()
                elif not detected and self._is_fullscreen:
                    self._is_fullscreen = False
                    if self._callback_exit:
                        self._callback_exit()
            except Exception:
                pass
            time.sleep(self._check_interval)

    def _check_fullscreen(self) -> bool:
        try:
            user32 = _get_user32()

            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return False

            # Ignorar ventanas del sistema, escritorio o barra de tareas
            cls_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls_buf, 256)
            if cls_buf.value in _IGNORED_WINDOW_CLASSES:
                return False

            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            monitor = user32.MonitorFromWindow(hwnd, _MONITOR_DEFAULTTONEAREST)
            if not monitor:
                return False

            mi = _MONITORINFO()
            mi.cbSize = ctypes.sizeof(_MONITORINFO)
            if not user32.GetMonitorInfoW(monitor, ctypes.byref(mi)):
                return False

            monitor_area = mi.rcMonitor

            return (
                rect.left <= monitor_area.left
                and rect.top <= monitor_area.top
                and rect.right >= monitor_area.right
                and rect.bottom >= monitor_area.bottom
            )
        except Exception:
            return False
