"""Icono en la bandeja del sistema."""

import os
import tempfile
import threading
from io import BytesIO
from typing import Callable, Optional

import pystray
from PIL import Image, ImageDraw, ImageFont

from screentime.config import ICON_PATH, get_app_name


def create_tray_icon_image(color: str = "#107C10") -> Image.Image:
    """Crea una imagen de icono para el tray dinámicamente."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.ellipse([2, 2, size - 2, size - 2], fill="#1a1a2e", outline=color, width=3)

    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except (OSError, IOError):
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), "S", font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (size - tw) // 2
    ty = (size - th) // 2 - 2
    draw.text((tx, ty), "S", fill=color, font=font)

    return img


def get_icon_path() -> str:
    """Obtiene la ruta del icono, creándolo si no existe."""
    if os.path.exists(ICON_PATH):
        return ICON_PATH

    img = create_tray_icon_image()
    temp_dir = tempfile.gettempdir()
    temp_icon = os.path.join(temp_dir, "screen_time_notifier.ico")
    img.save(temp_icon, format="ICO", sizes=[(16, 16), (32, 32), (64, 64)])
    return temp_icon


class TrayIcon:
    """Gestiona el icono de la bandeja del sistema."""

    def __init__(self):
        self._icon: Optional[pystray.Icon] = None
        self._running = False

        self._on_show: Optional[Callable] = None
        self._on_reset: Optional[Callable] = None
        self._on_pause_toggle: Optional[Callable] = None
        self._on_configure: Optional[Callable] = None
        self._on_autostart_toggle: Optional[Callable] = None
        self._on_quit: Optional[Callable] = None

        self._is_paused = False
        self._auto_start = False
        self._current_time = "00:00:00"

    def set_callbacks(self, **kwargs):
        self._on_show = kwargs.get("on_show")
        self._on_reset = kwargs.get("on_reset")
        self._on_pause_toggle = kwargs.get("on_pause_toggle")
        self._on_configure = kwargs.get("on_configure")
        self._on_autostart_toggle = kwargs.get("on_autostart_toggle")
        self._on_quit = kwargs.get("on_quit")

    def update_state(self, is_paused: bool, auto_start: bool, current_time: str):
        self._is_paused = is_paused
        self._auto_start = auto_start
        self._current_time = current_time
        if self._icon:
            status = "PAUSADO" if is_paused else "Activo"
            self._icon.title = f"{get_app_name()} — {status} — {current_time}"
            self._icon.menu = self._build_menu()

    def _build_menu(self) -> pystray.Menu:
        pause_text = "▶ Reanudar" if self._is_paused else "⏸ Pausar"
        autostart_text = "✓ Iniciar con Windows" if self._auto_start else "  Iniciar con Windows"

        return pystray.Menu(
            pystray.MenuItem(
                f"📊 Ver tiempo actual ({self._current_time})",
                lambda: self._safe_call(self._on_show),
                default=True,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "🔄 Reiniciar contador",
                lambda: self._safe_call(self._on_reset),
            ),
            pystray.MenuItem(
                pause_text,
                lambda: self._safe_call(self._on_pause_toggle),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "⚙ Configurar intervalo",
                lambda: self._safe_call(self._on_configure),
            ),
            pystray.MenuItem(
                autostart_text,
                lambda: self._safe_call(self._on_autostart_toggle),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "❌ Salir",
                lambda: self._safe_call(self._on_quit),
            ),
        )

    def _safe_call(self, callback: Optional[Callable]):
        if callback:
            try:
                callback()
            except Exception:
                pass

    def run(self):
        if self._running:
            return

        icon_image = create_tray_icon_image()

        self._icon = pystray.Icon(
            name="ScreenTimeNotifier",
            icon=icon_image,
            title=f"{get_app_name()} — Activo",
            menu=self._build_menu(),
        )

        self._running = True
        thread = threading.Thread(target=self._icon.run, daemon=True)
        thread.start()

    def stop(self):
        self._running = False
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None

    def update_icon(self, is_paused: bool = False):
        if self._icon:
            color = "#ff6b35" if is_paused else "#107C10"
            new_img = create_tray_icon_image(color)
            self._icon.icon = new_img
