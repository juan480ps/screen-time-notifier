"""Configuraciones y preferencias de la aplicación."""

import json
import os
import sys

from screentime import __app_name__, __version__

# ─── Rutas base ──────────────────────────────────────────────────────────────
_FROZEN = getattr(sys, "frozen", False)

# Assets empaquetados (read-only, extraídos por PyInstaller)
if _FROZEN:
    BUNDLE_DIR = sys._MEIPASS
else:
    BUNDLE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Datos del usuario ( writable, en AppData )
APP_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), __app_name__)

DATA_DIR = APP_DATA_DIR
ASSETS_DIR = os.path.join(BUNDLE_DIR, "assets")
SOUNDS_DIR = os.path.join(ASSETS_DIR, "sounds")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
CONFIG_FILE = os.path.join(DATA_DIR, "settings.json")
ICON_PATH = os.path.join(ASSETS_DIR, "icon.ico")
NOTIFY_SOUND = os.path.join(SOUNDS_DIR, "notify.mp3")

os.makedirs(DATA_DIR, exist_ok=True)

# ─── Configuración por defecto ──────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "interval_seconds": 1800,
    "auto_start": False,
    "sound_enabled": True,
    "notifications_paused": False,
    "warning_threshold_minutes": 120,
    "overlay_seconds": 8,
    "daily_goal_enabled": False,
    "daily_goal_hours": 8,
    "daily_goal_warn_pct": 80,
    "pomodoro_enabled": False,
    "pomodoro_work_minutes": 25,
    "pomodoro_break_minutes": 5,
    "pomodoro_long_break_minutes": 15,
    "pomodoro_cycles": 4,
    "screen_lock_enabled": False,
    "screen_lock_minutes": 240,
    "game_mode_enabled": False,
    "shutdown_enabled": False,
    "shutdown_mode": "hora",
    "shutdown_time": "23:00",
    "shutdown_minutes": 60,
    "shutdown_warn_minutes": 5,
    "start_minimized": True,
    "window_geometry": None,
    "last_update_check": 0,
}


def load_settings() -> dict:
    """Carga las configuraciones desde el archivo JSON."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # Migración: versiones previas guardaban screen_lock_hours.
            if "screen_lock_minutes" not in saved and "screen_lock_hours" in saved:
                saved["screen_lock_minutes"] = int(saved["screen_lock_hours"]) * 60
            return {**DEFAULT_SETTINGS, **saved}
        except (json.JSONDecodeError, IOError):
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict) -> bool:
    """Guarda las configuraciones en el archivo JSON."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        return True
    except IOError:
        return False


def get_app_name() -> str:
    """Nombre de la aplicación."""
    return __app_name__


def get_app_version() -> str:
    """Versión de la aplicación."""
    return __version__
