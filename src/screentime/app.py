"""Punto de entrada principal de Screen Time Notifier."""

import atexit
import csv
import ctypes
import os
import queue
import sys
import threading
from datetime import date
from typing import Callable

from screentime.config import get_app_name, get_app_version, load_settings, save_settings
from screentime.dialogs import IntervalDialog
from screentime.filelog import append_log
from screentime.fullscreen_detector import FullscreenDetector
from screentime.gui import MainGUI
from screentime.logger import UsageLogger
from screentime.notifier import ScreenTimeNotifier
from screentime.pomodoro import PomodoroState, PomodoroTimer
from screentime.shutdown import (
    COUNTDOWN,
    DEFAULT_GRACE_SECONDS,
    DEFAULT_POSTPONE_MINUTES,
    SHUTDOWN_MESSAGE,
    ShutdownScheduler,
    abort_os_shutdown,
    schedule_os_shutdown,
)
from screentime.theme import COLORS
from screentime.tray_icon import TrayIcon
from screentime.updater import check_for_update, download_and_update


def _log(msg: str):
    """Escribe un mensaje al log y a stdout."""
    append_log(msg)
    print(msg)


class ScreenTimeApp:
    """Clase principal que orquesta todos los componentes."""

    def __init__(self):
        self.settings = load_settings()
        self.logger = UsageLogger()
        self.notifier = ScreenTimeNotifier()
        self.gui = MainGUI(self.logger, self.notifier, self.settings)
        self.tray = TrayIcon()
        self.pomodoro = PomodoroTimer()
        self.fullscreen_detector = FullscreenDetector()
        self.shutdown = ShutdownScheduler()
        self._screen_lock_triggered = False
        self._os_shutdown_armed = False

        # Cola thread-safe para notificaciones desde el hilo del timer
        self._notification_queue = queue.Queue()
        # Cola de tareas que deben ejecutarse en el hilo principal de tkinter
        self._ui_tasks = queue.Queue()

        self.notifier.set_interval_seconds(self.settings["interval_seconds"])
        self.notifier.set_notification_callback(self._on_notification)

        self.shutdown.configure(
            enabled=self.settings.get("shutdown_enabled", False),
            mode=self.settings.get("shutdown_mode", "hora"),
            time_str=self.settings.get("shutdown_time", "23:00"),
            minutes=self.settings.get("shutdown_minutes", 60),
            warn_minutes=self.settings.get("shutdown_warn_minutes", 5),
        )
        self.shutdown.set_callbacks(
            on_warning=self._on_shutdown_warning,
            on_shutdown=self._on_shutdown_fire,
        )

        self.gui._on_interval_change = self._on_interval_change_from_gui
        self.gui._on_overlay_change = self._on_overlay_change_from_gui
        self.gui._on_pomodoro_start = self._start_pomodoro
        self.gui._on_pomodoro_stop = self._stop_pomodoro
        self.gui._on_pomodoro_skip = self._skip_pomodoro
        self.gui._on_export_csv = self._export_csv
        self.gui.set_daily_goal(self.settings.get("daily_goal_hours", 8))

        self.gui._on_daily_goal_toggle = self._toggle_daily_goal
        self.gui._on_daily_goal_change = self._on_daily_goal_change
        self.gui._on_pomodoro_toggle = self._toggle_pomodoro
        self.gui._on_game_mode_toggle = self._toggle_game_mode
        self.gui._on_screen_lock_toggle = self._toggle_screen_lock
        self.gui._on_screen_lock_hours_change = self._on_screen_lock_hours_change
        self.gui._on_shutdown_change = self._on_shutdown_change_from_gui
        self.gui._on_shutdown_now = self._on_shutdown_now
        self.gui._on_shutdown_postpone = self._on_shutdown_postpone
        self.gui._on_shutdown_cancel = self._on_shutdown_cancel
        self.gui._on_autostart_toggle = self._set_autostart
        self.gui._on_start_minimized_toggle = self._set_start_minimized

        self.pomodoro.configure(
            work_min=self.settings.get("pomodoro_work_minutes", 25),
            break_min=self.settings.get("pomodoro_break_minutes", 5),
            long_break_min=self.settings.get("pomodoro_long_break_minutes", 15),
            cycles=self.settings.get("pomodoro_cycles", 4),
        )
        self.pomodoro.set_callbacks(
            on_tick=self._on_pomodoro_tick,
            on_state_change=self._on_pomodoro_state_change,
        )

        if self.settings.get("game_mode_enabled", False):
            self.fullscreen_detector.set_callbacks(
                on_enter=self._on_fullscreen_enter,
                on_exit=self._on_fullscreen_exit,
            )
            self.fullscreen_detector.start()

        self.tray.set_callbacks(
            on_show=self._on_show_time,
            on_reset=self._on_reset,
            on_pause_toggle=self._on_pause_toggle,
            on_configure=self._on_configure,
            on_autostart_toggle=self._on_autostart_toggle,
            on_minimized_toggle=self._on_minimized_toggle,
            on_shutdown_toggle=self._on_shutdown_toggle,
            on_shutdown_now=self._on_shutdown_now,
            on_shutdown_postpone=self._on_shutdown_postpone,
            on_shutdown_cancel=self._on_shutdown_cancel,
            on_check_update=self._on_check_update,
            on_quit=self._on_quit,
        )

        self._tray_update_running = False
        atexit.register(self._cleanup)

    def run(self):
        _log(f"[{get_app_name()} v{get_app_version()}] Iniciando...")

        self.tray.run()
        self.notifier.start()
        self.shutdown.start()
        self._start_tray_updater()

        start_minimized = bool(self.settings.get("start_minimized", True))
        self.gui.create_window(start_minimized=start_minimized)
        self.gui.set_interval_from_settings(
            self.settings["interval_seconds"],
            self.settings.get("overlay_seconds", 8),
        )
        self.gui.set_toggles_from_settings(self.settings)

        # Iniciar polling de la cola de notificaciones en el hilo principal
        self._poll_notification_queue()

        if start_minimized:
            _log(f"[{get_app_name()}] Iniciado minimizado (ventana oculta).")
            self._notification_queue.put(
                ("Iniciado minimizado. Clic en el icono del tray para abrir la ventana.", False)
            )

        if self.shutdown.is_enabled:
            _log(f"[{get_app_name()}] {self.shutdown.status_text()}")

        # Verificar actualizaciones en background
        threading.Thread(target=self._startup_update_check, daemon=True).start()

        _log(f"[{get_app_name()}] Aplicacion en ejecucion.")
        interval_s = self.settings["interval_seconds"]
        if interval_s >= 3600:
            interval_str = f"{interval_s // 3600}h"
        elif interval_s >= 60:
            interval_str = f"{interval_s // 60}min"
        else:
            interval_str = f"{interval_s}s"
        _log(f"[{get_app_name()}] Intervalo: {interval_str}")

        try:
            self.gui.root.mainloop()
        except KeyboardInterrupt:
            self._on_quit()

    # ─── Cola de notificaciones (thread-safe) ───────────────────────────

    def _poll_notification_queue(self):
        """Polling en el hilo principal: revisa la cola cada 200ms."""
        try:
            while True:
                msg, check_lock = self._notification_queue.get_nowait()
                self._do_show_notification(msg, check_lock)
        except queue.Empty:
            pass

        try:
            while True:
                task = self._ui_tasks.get_nowait()
                try:
                    task()
                except Exception as e:
                    _log(f"[Error] Tarea UI: {e}")
        except queue.Empty:
            pass

        if self.gui.root:
            self.gui.root.after(200, self._poll_notification_queue)

    def _post_ui(self, task: Callable):
        """Agenda una tarea para que corra en el hilo principal de tkinter."""
        self._ui_tasks.put(task)

    # ─── Auto-actualizacion ──────────────────────────────────────────────

    def _startup_update_check(self):
        """Verifica actualizaciones al iniciar (en background)."""
        import time
        time.sleep(5)
        info = check_for_update()
        if isinstance(info, dict):
            self.tray.set_update_available(info["version"])
            _log(f"[Update] Nueva version disponible: {info['version']}")

    def _on_check_update(self):
        """Callback del tray: buscar e instalar actualizacion."""
        def _do():
            if not getattr(sys, "frozen", False):
                self._notification_queue.put(
                    ("La actualizacion automatica solo esta disponible en el ejecutable.", False)
                )
                return
            _log("[Update] Buscando actualizaciones...")
            info = check_for_update()
            if info is True:
                self._notification_queue.put(("Ya tienes la ultima version.", False))
                return
            if info is None:
                self._notification_queue.put(("Error al conectar con GitHub.", False))
                return

            self.tray.set_update_available(info["version"])
            _log(f"[Update] Descargando {info['version']}...")

            def _on_progress(downloaded, total):
                pct = int((downloaded / total) * 100) if total > 0 else 0
                _log(f"[Update] Descargando... {pct}%")

            ok = download_and_update(info, on_progress=_on_progress)
            if ok:
                _log("[Update] Actualizacion descargada. Reiniciando...")
                self._notification_queue.put(("Actualizacion instalada. Reiniciando...", False))
                import time
                time.sleep(2)
                os._exit(0)
            else:
                _log("[Update] Error al descargar la actualizacion.")
                self._notification_queue.put(("Error al descargar la actualizacion.", False))

        threading.Thread(target=_do, daemon=True).start()

    def _do_show_notification(self, message: str, check_lock: bool = True):
        """Ejecuta la notificacion en el hilo principal (seguro para tkinter)."""
        try:
            if self.settings["sound_enabled"]:
                ScreenTimeNotifier.play_notification_sound()
        except Exception as e:
            _log(f"[Error] Sonido: {e}")

        try:
            self._show_overlay(message)
        except Exception as e:
            _log(f"[Error] Overlay: {e}")

        if check_lock:
            try:
                self._check_screen_lock()
            except Exception as e:
                _log(f"[Error] Screen lock: {e}")

        _log(f"[Notificacion] {message}")

    # ─── Toggles ─────────────────────────────────────────────────────────

    def _toggle_daily_goal(self, enabled: bool):
        self.settings["daily_goal_enabled"] = enabled
        save_settings(self.settings)
        state = "activada" if enabled else "desactivada"
        _log(f"[Meta diaria] {state}.")

    def _on_daily_goal_change(self, hours: int):
        self.settings["daily_goal_hours"] = hours
        save_settings(self.settings)
        self.gui.set_daily_goal(hours)
        _log(f"[Meta diaria] Meta cambiada a {hours}h.")

    def _toggle_pomodoro(self, enabled: bool):
        self.settings["pomodoro_enabled"] = enabled
        save_settings(self.settings)
        state = "activado" if enabled else "desactivado"
        _log(f"[Pomodoro] Modo {state}.")
        if enabled and not self.pomodoro.is_running:
            self._start_pomodoro()
        elif not enabled and self.pomodoro.is_running:
            self._stop_pomodoro()

    def _toggle_game_mode(self, enabled: bool):
        self.settings["game_mode_enabled"] = enabled
        save_settings(self.settings)
        if enabled:
            self.fullscreen_detector.set_callbacks(
                on_enter=self._on_fullscreen_enter,
                on_exit=self._on_fullscreen_exit,
            )
            self.fullscreen_detector.start()
            _log("[Modo juego] Activado.")
        else:
            self.fullscreen_detector.stop()
            self.gui.game_status_dot.configure(fg=COLORS["text_secondary"])
            _log("[Modo juego] Desactivado.")

    def _toggle_screen_lock(self, enabled: bool):
        self.settings["screen_lock_enabled"] = enabled
        save_settings(self.settings)
        self._screen_lock_triggered = False
        state = "activado" if enabled else "desactivado"
        _log(f"[Bloqueo de pantalla] {state}.")

    def _on_screen_lock_hours_change(self, hours: int):
        self.settings["screen_lock_hours"] = hours
        save_settings(self.settings)
        self._screen_lock_triggered = False
        _log(f"[Bloqueo] Bloquear despues de {hours}h.")

    # ─── Apagado automático ──────────────────────────────────────────────

    def _on_shutdown_change_from_gui(self, config: dict):
        """El usuario cambió la programación del apagado desde la ventana."""
        is_countdown = config["mode"] == COUNTDOWN
        self.settings["shutdown_enabled"] = config["enabled"]
        self.settings["shutdown_mode"] = config["mode"]
        self.settings["shutdown_time"] = config["time"]
        self.settings["shutdown_minutes"] = config["minutes"]
        self.settings["shutdown_warn_minutes"] = config["warn_minutes"]
        save_settings(self.settings)

        # Si ya había un apagado pedido a Windows, se cancela antes de reprogramar
        had_os_shutdown = self._cancel_pending_os_shutdown()

        self.shutdown.configure(
            enabled=config["enabled"],
            mode=config["mode"],
            time_str=config["time"],
            minutes=config["minutes"],
            warn_minutes=config["warn_minutes"],
        )
        _log(f"[Apagado] {self.shutdown.status_text()}")
        self._post_ui(lambda: self.gui.set_shutdown_status(self.shutdown.status_text()))

        if config["enabled"]:
            if is_countdown:
                msg = f"El equipo se apagara en {config['minutes']} minutos."
            else:
                msg = f"El equipo se apagara a las {config['time']} (todos los dias)."
        elif had_os_shutdown:
            msg = "Apagado programado cancelado."
        else:
            return
        self._notification_queue.put((msg, False))

    def _on_shutdown_warning(self, remaining_seconds: float):
        """Callback del scheduler (hilo monitor): aviso previo al apagado."""
        minutes = max(1, int(round(remaining_seconds / 60.0)))
        self._notification_queue.put(
            (f"El equipo se apagara en {minutes} min. Cancelalo desde el menu del icono.", False)
        )
        _log(f"[Apagado] Aviso previo: faltan {minutes} min.")

    def _on_shutdown_fire(self):
        """Callback del scheduler (hilo monitor): pide el apagado a Windows."""
        self._os_shutdown_armed = schedule_os_shutdown(DEFAULT_GRACE_SECONDS, SHUTDOWN_MESSAGE)
        if self._os_shutdown_armed:
            msg = f"Apagando el equipo en {DEFAULT_GRACE_SECONDS} segundos. Cancelar: menu del icono."
            _log("[Apagado] Apagado programado (60 s de gracia).")
        else:
            msg = "No se pudo programar el apagado del equipo."
            _log("[Apagado] Error al programar el apagado del equipo.")
        self._notification_queue.put((msg, False))

        # La cuenta atrás se consume: se desactiva sola
        if self.shutdown.mode == COUNTDOWN:
            self.settings["shutdown_enabled"] = False
            save_settings(self.settings)
            self.shutdown.cancel()
            self._post_ui(lambda: self.gui.set_shutdown_enabled(False))

    def _on_shutdown_now(self):
        """Apaga el equipo en 60 s a petición del usuario (ventana o icono)."""
        self._os_shutdown_armed = schedule_os_shutdown(DEFAULT_GRACE_SECONDS, SHUTDOWN_MESSAGE)
        if self._os_shutdown_armed:
            msg = f"Apagando el equipo en {DEFAULT_GRACE_SECONDS} segundos. Cancelar: menu del icono."
        else:
            msg = "No se pudo programar el apagado del equipo."
        _log(f"[Apagado] {msg}")
        self._notification_queue.put((msg, False))

    def _on_shutdown_postpone(self):
        """Retrasa el apagado pendiente (ventana o icono del tray)."""
        if self.shutdown.postpone(DEFAULT_POSTPONE_MINUTES):
            msg = f"Apagado pospuesto {DEFAULT_POSTPONE_MINUTES} min."
            _log(f"[Apagado] Pospuesto: {self.shutdown.status_text()}")
            self._post_ui(lambda: self.gui.set_shutdown_status(self.shutdown.status_text()))
        else:
            msg = "No hay apagado programado para posponer."
        self._notification_queue.put((msg, False))

    def _on_shutdown_cancel(self):
        """Cancela el apagado pendiente y desactiva la programación."""
        self._cancel_pending_os_shutdown()
        self.shutdown.cancel()
        self.settings["shutdown_enabled"] = False
        save_settings(self.settings)
        self._post_ui(lambda: self.gui.set_shutdown_enabled(False))
        _log("[Apagado] Apagado cancelado y programacion desactivada.")
        self._notification_queue.put(("Apagado cancelado. La programacion quedo desactivada.", False))

    def _on_shutdown_toggle(self):
        """Alterna la programación desde el icono del tray."""
        enabled = not self.settings.get("shutdown_enabled", False)
        config = {
            "enabled": enabled,
            "mode": self.settings.get("shutdown_mode", "hora"),
            "time": self.settings.get("shutdown_time", "23:00"),
            "minutes": self.settings.get("shutdown_minutes", 60),
            "warn_minutes": self.settings.get("shutdown_warn_minutes", 5),
        }
        self._post_ui(lambda: self.gui.set_shutdown_enabled(enabled))
        self._on_shutdown_change_from_gui(config)

    def _cancel_pending_os_shutdown(self) -> bool:
        """Aborta el apagado que Windows tiene en cuenta atrás, si existe."""
        if not self._os_shutdown_armed:
            return False
        abort_os_shutdown()
        self._os_shutdown_armed = False
        return True

    def _update_shutdown_status(self):
        """Refresca el texto de estado en la ventana (solo hilo principal)."""
        if self.gui.root:
            try:
                self.gui.set_shutdown_status(self.shutdown.status_text())
            except Exception:
                pass

    def _on_notification(self):
        """Callback desde el hilo del timer — solo encola."""
        elapsed = self.logger.get_elapsed_formatted()
        elapsed_minutes = self.logger.get_elapsed_minutes()

        goal_enabled = self.settings.get("daily_goal_enabled", False)
        goal_hours = self.settings.get("daily_goal_hours", 8)
        warn_pct = self.settings.get("daily_goal_warn_pct", 80)
        total_today = self.logger.get_today_stats()["total_seconds"]
        goal_reached_pct = (total_today / (goal_hours * 3600)) * 100

        if goal_enabled and goal_reached_pct >= 100:
            message = f"Meta diaria alcanzada! Llevas {elapsed} conectado hoy."
        elif goal_enabled and goal_reached_pct >= warn_pct:
            message = f"Llevas {elapsed}. Estas al {int(goal_reached_pct)}% de tu meta diaria."
        else:
            is_warning = elapsed_minutes >= self.settings["warning_threshold_minutes"]
            message = self.notifier.get_random_message(elapsed, is_warning)

        self._notification_queue.put((message, True))

    def _show_overlay(self, message: str):
        try:
            import tkinter as tk

            overlay = tk.Toplevel()
            overlay.overrideredirect(True)
            overlay.attributes("-topmost", True)
            overlay.attributes("-alpha", 0.95)
            overlay.configure(bg="#107C10")

            sw = overlay.winfo_screenwidth()
            overlay.geometry(f"380x90+{sw - 400}+20")

            inner = tk.Frame(overlay, bg="#1a1a2e", padx=12, pady=8)
            inner.pack(fill=tk.BOTH, expand=True)

            tk.Label(inner, text="Screen Time", font=("Segoe UI", 10, "bold"),
                     bg="#1a1a2e", fg="#107C10").pack(anchor="w")
            tk.Label(inner, text=message, font=("Segoe UI", 9),
                     bg="#1a1a2e", fg="#e0e0e0", wraplength=340, justify="left",
                     anchor="w").pack(fill=tk.X, pady=(4, 0))

            overlay_ms = self.settings.get("overlay_seconds", 8) * 1000
            overlay.after(overlay_ms, lambda: overlay.destroy())
            overlay.bind("<Button-1>", lambda e: overlay.destroy())
        except Exception as e:
            _log(f"[Error] Overlay: {e}")

    def _start_tray_updater(self):
        self._tray_update_running = True
        self._update_tray()

    def _update_tray(self):
        if not self._tray_update_running:
            return

        try:
            elapsed = self.logger.get_elapsed_short()
            self.tray.update_state(
                is_paused=self.notifier.is_paused,
                auto_start=self.settings.get("auto_start", False),
                current_time=elapsed,
                shutdown_status=self.shutdown.short_status(),
                shutdown_enabled=self.shutdown.is_enabled,
                start_minimized=self.settings.get("start_minimized", True),
            )
            self._update_shutdown_status()
        except Exception:
            pass

        if self.gui.root:
            # Cada segundo: la cuenta atrás del apagado debe latir en vivo
            self.gui.root.after(1000, self._update_tray)

    # ─── Acciones del menu ───────────────────────────────────────────────

    def _on_show_time(self):
        if self.gui.is_visible:
            self.gui.hide()
        else:
            self.gui.show()

    def _on_reset(self):
        self.logger.save_session()
        self.logger.reset()
        _log("[Accion] Contador reiniciado.")
        self._notification_queue.put(("Contador reiniciado. Nueva sesion!", False))

    def _on_pause_toggle(self):
        if self.notifier.is_paused:
            self.notifier.resume()
            self.logger.resume()
            self.gui.status_var.set("Activo")
            _log("[Accion] Notificaciones reanudadas.")
            self._notification_queue.put(("Notificaciones reanudadas.", False))
        else:
            self.notifier.pause()
            self.logger.pause()
            self.gui.status_var.set("Pausado")
            _log("[Accion] Notificaciones pausadas.")
            self._notification_queue.put(("Notificaciones pausadas.", False))

    def _on_configure(self):
        dialog = IntervalDialog(self.gui.root, self.settings["interval_seconds"])
        new_interval = dialog.show()
        if new_interval is not None:
            self.settings["interval_seconds"] = new_interval
            save_settings(self.settings)
            self.notifier.set_interval_seconds(new_interval)
            if new_interval >= 3600:
                val = new_interval // 3600
                unit = "hora" if val == 1 else "horas"
            elif new_interval >= 60:
                val = new_interval // 60
                unit = "minuto" if val == 1 else "minutos"
            else:
                val = new_interval
                unit = "segundo" if val == 1 else "segundos"
            _log(f"[Accion] Intervalo cambiado a {val} {unit}.")
            self._notification_queue.put((f"Intervalo cambiado a {val} {unit}.", False))

    def _on_interval_change_from_gui(self, seconds: int):
        self.settings["interval_seconds"] = seconds
        save_settings(self.settings)
        self.notifier.set_interval_seconds(seconds)
        if seconds >= 3600:
            val = seconds // 3600
            unit = "hora" if val == 1 else "horas"
        elif seconds >= 60:
            val = seconds // 60
            unit = "minuto" if val == 1 else "minutos"
        else:
            val = seconds
            unit = "segundo" if val == 1 else "segundos"
        _log(f"[Accion] Intervalo cambiado a {val} {unit}.")
        self._notification_queue.put((f"Intervalo cambiado a {val} {unit}.", False))

    def _on_overlay_change_from_gui(self, seconds: int):
        self.settings["overlay_seconds"] = seconds
        save_settings(self.settings)
        _log(f"[Accion] Duracion del popup cambiada a {seconds}s.")

    # ─── Pomodoro ────────────────────────────────────────────────────────

    def _start_pomodoro(self):
        self.pomodoro.start()
        _log("[Pomodoro] Iniciado.")

    def _stop_pomodoro(self):
        self.pomodoro.stop()
        self.gui.pomodoro_state_var.set("Inactivo")
        self.gui.pomodoro_timer_var.set("00:00")
        self.gui.pomodoro_cycle_var.set("0/4")
        _log("[Pomodoro] Detenido.")

    def _skip_pomodoro(self):
        self.pomodoro.skip()

    def _on_pomodoro_tick(self, state, remaining, cycle, total):
        # Se ejecuta en el hilo del temporizador: solo se calculan los textos
        # y la actualización de tkinter se agenda en el hilo principal.
        remaining_fmt = self.pomodoro.get_remaining_formatted()
        self._post_ui(lambda: self._apply_pomodoro_tick(remaining_fmt, cycle, total))

    def _apply_pomodoro_tick(self, remaining_fmt: str, cycle: int, total: int):
        try:
            self.gui.pomodoro_timer_var.set(remaining_fmt)
            self.gui.pomodoro_cycle_var.set(f"{cycle}/{total}")
        except Exception:
            pass

    def _on_pomodoro_state_change(self, state, cycle, total):
        # Hilo del temporizador: encolar comida a la UI y notificaciones.
        label = self.pomodoro.get_state_label()
        remaining_fmt = self.pomodoro.get_remaining_formatted()
        self._post_ui(lambda: self._apply_pomodoro_state(label, cycle, total))

        if state == PomodoroState.WORK:
            self._notification_queue.put((f"Pomodoro: A trabajar! Ciclo {cycle}/{total}", False))
        elif state == PomodoroState.BREAK:
            self._notification_queue.put((f"Pomodoro: Descanso ({remaining_fmt})", False))
        elif state == PomodoroState.LONG_BREAK:
            self._notification_queue.put((f"Pomodoro: Descanso largo! ({remaining_fmt})", False))

    def _apply_pomodoro_state(self, label: str, cycle: int, total: int):
        try:
            self.gui.pomodoro_state_var.set(label)
            self.gui.pomodoro_cycle_var.set(f"{cycle}/{total}")
        except Exception:
            pass

    # ─── Modo juego ──────────────────────────────────────────────────────

    def _on_fullscreen_enter(self):
        if self.settings.get("game_mode_enabled", False):
            self.gui.game_status_dot.configure(fg=COLORS["accent_green_light"])
            _log("[Modo Juego] Pantalla completa detectada.")

    def _on_fullscreen_exit(self):
        if self.settings.get("game_mode_enabled", False):
            self.gui.game_status_dot.configure(fg=COLORS["text_secondary"])
            _log("[Modo Juego] Pantalla completa terminada.")

    # ─── Bloqueo de pantalla ─────────────────────────────────────────────

    def _check_screen_lock(self):
        if not self.settings.get("screen_lock_enabled", False):
            return
        lock_hours = self.settings.get("screen_lock_hours", 4)
        lock_seconds = lock_hours * 3600
        elapsed = self.logger.get_elapsed_seconds()
        if elapsed >= lock_seconds and not self._screen_lock_triggered:
            self._screen_lock_triggered = True
            self._show_screen_lock_overlay()

    def _show_screen_lock_overlay(self):
        try:
            import tkinter as tk

            overlay = tk.Toplevel()
            overlay.overrideredirect(True)
            overlay.attributes("-topmost", True)
            overlay.configure(bg="#000000")
            overlay.geometry(f"{overlay.winfo_screenwidth()}x{overlay.winfo_screenheight()}+0+0")

            frame = tk.Frame(overlay, bg="#000000")
            frame.pack(fill=tk.BOTH, expand=True)

            tk.Label(
                frame, text="Hora de descansar!", font=("Segoe UI", 24, "bold"),
                bg="#000000", fg="#107C10",
            ).pack(pady=(80, 10))
            tk.Label(
                frame,
                text="Llevas mucho tiempo frente a la pantalla.\nEstira las piernas, descansa la vista.",
                font=("Segoe UI", 14), bg="#000000", fg="#e0e0e0", justify="center",
            ).pack(pady=20)

            elapsed = self.logger.get_elapsed_formatted()
            tk.Label(
                frame, text=f"Tiempo conectado: {elapsed}", font=("Segoe UI", 12),
                bg="#000000", fg="#ff6b35",
            ).pack()

            tk.Button(
                frame, text="   Continuar   ",
                font=("Segoe UI", 14, "bold"),
                bg="#107C10", fg="white", padx=20, pady=10,
                command=lambda: [overlay.destroy(), self._reset_screen_lock()],
            ).pack(pady=40)

            overlay.bind("<Escape>", lambda e: [overlay.destroy(), self._reset_screen_lock()])
        except Exception as e:
            _log(f"[Error] Screen lock overlay: {e}")

    def _reset_screen_lock(self):
        self._screen_lock_triggered = False
        self.logger.reset()
        _log("[Bloqueo] Contador reiniciado.")

    # ─── Exportar CSV ────────────────────────────────────────────────────

    def _export_csv(self):
        try:
            from tkinter import filedialog

            data = self.logger.get_history()
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
                title="Exportar historial",
                initialfile=f"screen_time_{date.today().isoformat()}.csv",
            )
            if not file_path:
                return

            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Fecha", "Sesiones", "Total (segundos)", "Total (horas)"])

                for day_str, day_data in sorted(data.get("daily_sessions", {}).items()):
                    total_s = day_data.get("total_seconds", 0)
                    sessions = len(day_data.get("sessions", []))
                    hours = round(total_s / 3600, 2)
                    writer.writerow([day_str, sessions, total_s, hours])

            _log(f"[Export] Historial exportado a: {file_path}")
            self._notification_queue.put((f"Historial exportado a {os.path.basename(file_path)}", False))
        except Exception as e:
            _log(f"[Export] Error: {e}")

    def _on_autostart_toggle(self):
        """Alterna el inicio con Windows desde el icono del tray."""
        self._set_autostart(not self.settings.get("auto_start", False))

    def _set_autostart(self, enable: bool):
        self.settings["auto_start"] = bool(enable)
        save_settings(self.settings)
        self._set_windows_autostart(bool(enable))
        self._post_ui(lambda: self.gui.set_autostart(bool(enable)))

        estado = "activado" if enable else "desactivado"
        _log(f"[Accion] Inicio automatico {estado}.")
        self._notification_queue.put((f"Inicio automatico {estado}.", False))

    def _on_minimized_toggle(self):
        """Alterna el inicio minimizado desde el icono del tray."""
        self._set_start_minimized(not self.settings.get("start_minimized", True))

    def _set_start_minimized(self, enable: bool):
        """Guarda si la ventana debe abrirse o no al iniciar la aplicacion."""
        self.settings["start_minimized"] = bool(enable)
        save_settings(self.settings)
        self._post_ui(lambda: self.gui.set_start_minimized(bool(enable)))

        msg = (
            "Listo: la proxima vez arrancara minimizado (solo el icono del tray)."
            if enable
            else "Listo: la proxima vez se abrira la ventana al iniciar."
        )
        _log(f"[Accion] Inicio minimizado {'activado' if enable else 'desactivado'}.")
        self._notification_queue.put((msg, False))

    def _set_windows_autostart(self, enable: bool):
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)

            app_name = get_app_name()
            if enable:
                if getattr(sys, "frozen", False):
                    exe_path = sys.executable
                else:
                    exe_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass

            winreg.CloseKey(key)
        except Exception as e:
            _log(f"[Error] No se pudo configurar inicio automatico: {e}")

    def _on_quit(self):
        _log(f"[{get_app_name()}] Cerrando aplicacion...")
        self._tray_update_running = False
        self.notifier.stop()
        self.pomodoro.stop()
        self.fullscreen_detector.stop()
        self.shutdown.stop()
        if self._cancel_pending_os_shutdown():
            _log("[Apagado] Apagado pendiente cancelado al cerrar la aplicacion.")
        self.logger.save_session()
        self.settings["window_geometry"] = self.gui.get_geometry()
        save_settings(self.settings)
        self.tray.stop()
        self.gui.destroy()
        os._exit(0)

    def _cleanup(self):
        try:
            self.logger.save_session()
        except Exception:
            pass


_SINGLE_INSTANCE_MUTEX = None


def check_single_instance():
    """Verifica que no haya otra instancia de la app ejecutandose."""
    global _SINGLE_INSTANCE_MUTEX
    error_already_exists = 183
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        _SINGLE_INSTANCE_MUTEX = kernel32.CreateMutexW(None, False, "ScreenTimeNotifier_SingleInstance")
        if ctypes.get_last_error() == error_already_exists:
            _log("Ya hay una instancia ejecutandose.")
            ctypes.windll.user32.MessageBoxW(
                0,
                "Screen Time Notifier ya esta corriendo (revisa el icono en la "
                "bandeja del sistema, puede estar oculto). Cierra desde ahi "
                "antes de volver a abrirla.",
                "Screen Time Notifier",
                0x40,
            )
            sys.exit(0)
    except Exception:
        pass


def main():
    """Funcion principal de entrada."""
    check_single_instance()
    app = ScreenTimeApp()
    app.run()


if __name__ == "__main__":
    main()
