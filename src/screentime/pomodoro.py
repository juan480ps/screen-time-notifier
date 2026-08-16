"""Modo Pomodoro integrado."""

import threading
import time
from typing import Optional, Callable
from enum import Enum


class PomodoroState(Enum):
    IDLE = "idle"
    WORK = "work"
    BREAK = "break"
    LONG_BREAK = "long_break"


class PomodoroTimer:
    """Temporizador Pomodoro con ciclos configurables."""

    def __init__(self):
        self._running = False
        self._state = PomodoroState.IDLE
        self._thread: Optional[threading.Thread] = None
        self._current_cycle = 0
        self._total_cycles = 4
        self._work_seconds = 25 * 60
        self._break_seconds = 5 * 60
        self._long_break_seconds = 15 * 60
        self._remaining_seconds = 0
        self._on_tick: Optional[Callable] = None
        self._on_state_change: Optional[Callable] = None

    @property
    def state(self) -> PomodoroState:
        return self._state

    @property
    def remaining_seconds(self) -> int:
        return self._remaining_seconds

    @property
    def current_cycle(self) -> int:
        return self._current_cycle

    @property
    def total_cycles(self) -> int:
        return self._total_cycles

    @property
    def is_running(self) -> bool:
        return self._running and self._state != PomodoroState.IDLE

    def configure(self, work_min: int = 25, break_min: int = 5,
                  long_break_min: int = 15, cycles: int = 4):
        self._work_seconds = max(1, work_min) * 60
        self._break_seconds = max(1, break_min) * 60
        self._long_break_seconds = max(1, long_break_min) * 60
        self._total_cycles = max(1, cycles)

    def set_callbacks(self, on_tick: Callable = None, on_state_change: Callable = None):
        self._on_tick = on_tick
        self._on_state_change = on_state_change

    def start(self):
        if self._running:
            return
        self._current_cycle = 1
        self._start_work()

    def stop(self):
        self._running = False
        self._state = PomodoroState.IDLE
        self._remaining_seconds = 0

    def skip(self):
        if self._state == PomodoroState.WORK:
            self._on_work_end()
        elif self._state in (PomodoroState.BREAK, PomodoroState.LONG_BREAK):
            self._on_break_end()

    def _start_work(self):
        self._state = PomodoroState.WORK
        self._remaining_seconds = self._work_seconds
        self._running = True
        self._notify_state_change()
        self._start_countdown()

    def _start_break(self, is_long: bool = False):
        self._state = PomodoroState.LONG_BREAK if is_long else PomodoroState.BREAK
        self._remaining_seconds = self._long_break_seconds if is_long else self._break_seconds
        self._notify_state_change()
        self._start_countdown()

    def _start_countdown(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._countdown_loop, daemon=True)
        self._thread.start()

    def _countdown_loop(self):
        while self._running and self._remaining_seconds > 0:
            if self._on_tick:
                self._on_tick(self._state, self._remaining_seconds, self._current_cycle, self._total_cycles)
            time.sleep(1)
            self._remaining_seconds -= 1

        if self._running:
            if self._state == PomodoroState.WORK:
                self._on_work_end()
            elif self._state in (PomodoroState.BREAK, PomodoroState.LONG_BREAK):
                self._on_break_end()

    def _on_work_end(self):
        if self._current_cycle >= self._total_cycles:
            self._start_break(is_long=True)
        else:
            self._start_break(is_long=False)

    def _on_break_end(self):
        if self._state == PomodoroState.LONG_BREAK:
            self._current_cycle = 1
        else:
            self._current_cycle += 1
        self._start_work()

    def _notify_state_change(self):
        if self._on_state_change:
            self._on_state_change(self._state, self._current_cycle, self._total_cycles)

    def get_remaining_formatted(self) -> str:
        m = self._remaining_seconds // 60
        s = self._remaining_seconds % 60
        return f"{m:02d}:{s:02d}"

    def get_state_label(self) -> str:
        labels = {
            PomodoroState.IDLE: "Inactivo",
            PomodoroState.WORK: "Trabajo",
            PomodoroState.BREAK: "Descanso",
            PomodoroState.LONG_BREAK: "Descanso largo",
        }
        return labels.get(self._state, "")
