"""Apagado automático programado del equipo (Windows)."""

import subprocess
import sys
import threading
from datetime import datetime, timedelta
from typing import Callable, Optional

# Evita que Windows abra una consola al lanzar shutdown.exe
_CREATE_NO_WINDOW = 0x08000000

FIXED_TIME = "hora"
COUNTDOWN = "temporizador"

SHUTDOWN_MESSAGE = "Apagado programado por Screen Time Notifier"
DEFAULT_GRACE_SECONDS = 60
DEFAULT_POSTPONE_MINUTES = 10


def _run_shutdown_command(args: list) -> bool:
    """Ejecuta shutdown.exe sin mostrar ventana. Devuelve True si hubo éxito."""
    try:
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = _CREATE_NO_WINDOW
        result = subprocess.run(args, capture_output=True, check=False, **kwargs)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def schedule_os_shutdown(seconds: int = DEFAULT_GRACE_SECONDS, message: str = SHUTDOWN_MESSAGE) -> bool:
    """Pide a Windows apagar el equipo dentro de N segundos (cancelable con shutdown /a)."""
    try:
        seconds = max(0, int(seconds))
    except (TypeError, ValueError):
        seconds = DEFAULT_GRACE_SECONDS

    args = ["shutdown", "/s", "/t", str(seconds)]
    if message:
        args += ["/c", message[:512]]
    return _run_shutdown_command(args)


def abort_os_shutdown() -> bool:
    """Cancela un apagado pendiente del sistema. False si no había ninguno."""
    return _run_shutdown_command(["shutdown", "/a"])


def format_remaining(seconds: float) -> str:
    """Formatea una cuenta atrás en algo legible: '2h 14m 59s', '45m 10s', '8s'."""
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


class ShutdownScheduler:
    """Calcula cuándo apagar el equipo, avisa antes y dispara el apagado.

    Un único hilo monitor revisa el estado cada segundo, así que reprogramar
    o cancelar no crea hilos nuevos. Los callbacks se ejecutan desde ese hilo:
    quien los reciba debe pasar por la cola de la UI antes de tocar tkinter.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._enabled = False
        self._mode = FIXED_TIME
        self._time_str = "23:00"
        self._minutes = 60
        self._warn_seconds = 300
        self._target: Optional[datetime] = None
        self._warned = False
        self._on_warning: Optional[Callable] = None
        self._on_shutdown: Optional[Callable] = None

    # ─── Estado ──────────────────────────────────────────────────────────

    @property
    def is_enabled(self) -> bool:
        with self._lock:
            return self._enabled

    @property
    def mode(self) -> str:
        with self._lock:
            return self._mode

    @property
    def target(self) -> Optional[datetime]:
        with self._lock:
            return self._target

    @property
    def is_armed(self) -> bool:
        with self._lock:
            return self._enabled and self._target is not None

    def seconds_remaining(self) -> Optional[float]:
        with self._lock:
            if not self._enabled or self._target is None:
                return None
            target = self._target
        return (target - datetime.now()).total_seconds()

    def status_text(self) -> str:
        """Texto completo para la ventana principal."""
        with self._lock:
            enabled = self._enabled
            target = self._target
            mode = self._mode
            time_str = self._time_str

        if not enabled:
            return "Desactivado"
        if target is None:
            return "Hora no válida"
        remaining = format_remaining((target - datetime.now()).total_seconds())
        if mode == COUNTDOWN:
            return f"Apagado en {remaining}"
        return f"Apagado a las {time_str} (faltan {remaining})"

    def short_status(self) -> str:
        """Texto compacto para el menú del icono del tray."""
        with self._lock:
            enabled = self._enabled
            target = self._target
            mode = self._mode
            time_str = self._time_str

        if not enabled:
            return "desactivado"
        if target is None:
            return "hora no válida"
        remaining = format_remaining((target - datetime.now()).total_seconds())
        if mode == COUNTDOWN:
            return f"en {remaining}"
        return f"{time_str} (faltan {remaining})"

    def set_callbacks(self, on_warning: Optional[Callable] = None, on_shutdown: Optional[Callable] = None):
        """on_warning(segundos_restantes) avisa antes; on_shutdown() apaga el equipo."""
        self._on_warning = on_warning
        self._on_shutdown = on_shutdown

    def configure(
        self,
        enabled: bool,
        mode: str = FIXED_TIME,
        time_str: str = "23:00",
        minutes: int = 60,
        warn_minutes: int = 5,
    ) -> None:
        """Aplica la configuración. Solo recalcula la hora objetivo si cambió el horario."""
        try:
            minutes = max(1, int(minutes))
        except (TypeError, ValueError):
            minutes = 60
        try:
            warn_minutes = max(0, int(warn_minutes))
        except (TypeError, ValueError):
            warn_minutes = 5

        mode = COUNTDOWN if mode == COUNTDOWN else FIXED_TIME
        time_str = time_str or "23:00"

        with self._lock:
            schedule_changed = mode != self._mode or time_str != self._time_str or minutes != self._minutes
            self._mode = mode
            self._time_str = time_str
            self._minutes = minutes
            self._warn_seconds = warn_minutes * 60
            self._enabled = bool(enabled)

            if not self._enabled:
                self._target = None
                self._warned = False
            elif schedule_changed or self._target is None:
                self._target = self._compute_target_locked()
                self._warned = False

        if self._enabled:
            # Tras dispararse una cuenta atrás el hilo monitor termina solo;
            # hay que reactivarlo para que una nueva programación sí se cumpla.
            self.start()

    def cancel(self) -> None:
        """Desactiva la programación y descarta la cuenta atrás."""
        with self._lock:
            self._enabled = False
            self._target = None
            self._warned = False

    def postpone(self, minutes: int = DEFAULT_POSTPONE_MINUTES) -> bool:
        """Retrasa el apagado pendiente N minutos sin desactivarlo.

        Rearma el aviso previo para que vuelva a avisar si aún falta
        más que el umbral. Devuelve False si no había nada programado.
        """
        try:
            minutes = max(1, int(minutes))
        except (TypeError, ValueError):
            minutes = DEFAULT_POSTPONE_MINUTES

        with self._lock:
            if not self._enabled or self._target is None:
                return False
            self._target = self._target + timedelta(minutes=minutes)
            self._warned = False
        return True

    def _compute_target_locked(self) -> Optional[datetime]:
        """Siguiente momento de apagado (hoy o mañana) o cuenta atrás desde ahora."""
        now = datetime.now()

        if self._mode == COUNTDOWN:
            return now + timedelta(minutes=self._minutes)

        try:
            hour_str, minute_str = self._time_str.split(":")
            hour, minute = int(hour_str), int(minute_str)
        except (ValueError, AttributeError):
            return None
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None

        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target

    # ─── Hilo monitor ────────────────────────────────────────────────────

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor, name="shutdown-scheduler", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        thread = self._thread
        self._thread = None
        if thread and thread.is_alive():
            thread.join(timeout=2)

    def _monitor(self):
        while not self._stop_event.wait(1.0):
            with self._lock:
                if not self._enabled or self._target is None:
                    continue
                target = self._target
                should_warn = not self._warned and self._warn_seconds > 0
                warn_seconds = self._warn_seconds
                mode = self._mode

            remaining = (target - datetime.now()).total_seconds()

            if should_warn and remaining <= warn_seconds:
                with self._lock:
                    self._warned = True
                self._fire(self._on_warning, max(0.0, remaining))

            if remaining <= 0:
                self._fire(self._on_shutdown)
                with self._lock:
                    if mode == FIXED_TIME:
                        # Vuelve a programarse para el día siguiente (si el PC sigue encendido).
                        self._target = self._compute_target_locked()
                        self._warned = False
                    else:
                        # La cuenta atrás es de una sola vez.
                        self._target = None
                        self._enabled = False
                    keep_running = self._enabled
                if not keep_running:
                    return

    @staticmethod
    def _fire(callback: Optional[Callable], *args):
        if callback:
            try:
                callback(*args)
            except Exception:
                pass
