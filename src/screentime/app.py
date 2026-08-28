"""Punto de entrada principal de Screen Time Notifier."""

import csv
import os
import sys
import ctypes
import atexit
import queue
import threading
from datetime import date

from screentime.config import load_settings, save_settings, get_app_name, get_app_version, DATA_DIR
from screentime.logger import UsageLogger
from screentime.notifier import ScreenTimeNotifier
from screentime.gui import MainGUI, IntervalDialog, COLORS
from screentime.tray_icon import TrayIcon
from screentime.pomodoro import PomodoroTimer, PomodoroState
from screentime.fullscreen_detector import FullscreenDetector
from screentime.updater import check_for_update, download_and_update

LOG_FILE = os.path.join(DATA_DIR, "app.log")


def _log(msg: str):
    """Escribe un mensaje al log y a stdout."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
    except Exception:
        pass
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
        self._screen_lock_triggered = False

        # Cola thread-safe para notificaciones desde el hilo del timer
        self._notification_queue = queue.Queue()

        self.notifier.set_interval_seconds(self.settings["interval_seconds"])
        self.notifier.set_notification_callback(self._on_notification)

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
            on_check_update=self._on_check_update,
            on_quit=self._on_quit,
        )

        self._tray_update_running = False
        atexit.register(self._cleanup)

    def run(self):
        _log(f"[{get_app_name()} v{get_app_version()}] Iniciando...")

        self.tray.run()
        self.notifier.start()
        self._start_tray_updater()

        self.gui.create_window()
        self.gui.set_interval_from_settings(
            self.settings["interval_seconds"],
            self.settings.get("overlay_seconds", 8),
        )
        self.gui.set_toggles_from_settings(self.settings)

        # Iniciar polling de la cola de notificaciones en el hilo principal
        self._poll_notification_queue()

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
        if self.gui.root:
            self.gui.root.after(200, self._poll_notification_queue)

    # ─── Auto-actualizacion ──────────────────────────────────────────────

    def _startup_update_check(self):
        """Verifica actualizaciones al iniciar (en background)."""
        import time
        time.sleep(5)
        info = check_for_update()
        if info:
            self.tray.set_update_available(info["version"])
            _log(f"[Update] Nueva version disponible: {info['version']}")

    def _on_check_update(self):
        """Callback del tray: buscar e instalar actualizacion."""
        def _do():
            info = check_for_update()
            if not info:
                self._notification_queue.put(("Ya tienes la ultima version.", False))
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

    # ─── Toggles ─────────────────────────────────────────────────────────
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
            )
        except Exception:
            pass

        if self.gui.root:
            self.gui.root.after(2000, self._update_tray)

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
        try:
            self.gui.pomodoro_timer_var.set(self.pomodoro.get_remaining_formatted())
            self.gui.pomodoro_cycle_var.set(f"{cycle}/{total}")
        except Exception:
            pass

    def _on_pomodoro_state_change(self, state, cycle, total):
        try:
            label = self.pomodoro.get_state_label()
            self.gui.pomodoro_state_var.set(label)
            self.gui.pomodoro_cycle_var.set(f"{cycle}/{total}")
            if state == PomodoroState.WORK:
                self._notification_queue.put((f"Pomodoro: A trabajar! Ciclo {cycle}/{total}", False))
            elif state == PomodoroState.BREAK:
                self._notification_queue.put((f"Pomodoro: Descanso ({self.pomodoro.get_remaining_formatted()})", False))
            elif state == PomodoroState.LONG_BREAK:
                self._notification_queue.put((f"Pomodoro: Descanso largo! ({self.pomodoro.get_remaining_formatted()})", False))
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

            tk.Label(frame, text="Hora de descansar!", font=("Segoe UI", 24, "bold"), bg="#000000", fg="#107C10").pack(pady=(80, 10))
            tk.Label(
                frame,
                text="Llevas mucho tiempo frente a la pantalla.\nEstira las piernas, descansa la vista.",
                font=("Segoe UI", 14), bg="#000000", fg="#e0e0e0", justify="center",
            ).pack(pady=20)

            elapsed = self.logger.get_elapsed_formatted()
            tk.Label(frame, text=f"Tiempo conectado: {elapsed}", font=("Segoe UI", 12), bg="#000000", fg="#ff6b35").pack()

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

            data = self.logger._load_data()
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
        self.settings["auto_start"] = not self.settings["auto_start"]
        save_settings(self.settings)
        self._set_windows_autostart(self.settings["auto_start"])

        estado = "activado" if self.settings["auto_start"] else "desactivado"
        _log(f"[Accion] Inicio automatico {estado}.")
        self._notification_queue.put((f"Inicio automatico {estado}.", False))

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


def check_single_instance():
    """Verifica que no haya otra instancia de la app ejecutandose."""
    try:
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "ScreenTimeNotifier_SingleInstance")
        if ctypes.windll.kernel32.GetLastError() == 183:
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
