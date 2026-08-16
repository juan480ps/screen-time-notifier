"""Detección de modo juego / pantalla completa."""

import ctypes
import threading
import time
from typing import Optional, Callable


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
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return False

            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            monitor = user32.MonitorFromWindow(hwnd, 1)
            mi = ctypes.wintypes.MONITORINFO()
            mi.cbSize = ctypes.sizeof(ctypes.wintypes.MONITORINFO)
            user32.GetMonitorInfoW(monitor, ctypes.byref(mi))

            work_area = mi.rcWork

            return (
                rect.left <= work_area.left
                and rect.top <= work_area.top
                and rect.right >= work_area.right
                and rect.bottom >= work_area.bottom
            )
        except Exception:
            return False
