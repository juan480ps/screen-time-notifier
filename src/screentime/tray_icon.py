"""Icono en la bandeja del sistema."""

import os
import tempfile
import threading
from typing import Callable, Optional

import pystray
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

from screentime.config import ICON_PATH, get_app_name
from screentime.shutdown import DEFAULT_POSTPONE_MINUTES

# Paletas del icono: (verde/activo) y (naranja/pausado).
_TRAY_PALETTES = {
    "#107C10": ("#00E676", "#00B0FF"),
    "#ff6b35": ("#FFC400", "#FF3D71"),
}


def create_tray_icon_image(color: str = "#107C10") -> Image.Image:
    """Crea el icono del tray: cuadrado redondeado con degradado y 'S'."""
    s = 256
    from_hex, to_hex = _TRAY_PALETTES.get(color, (color, color))

    gv = Image.linear_gradient("L").resize((s, s))
    gh = gv.transpose(Image.ROTATE_90)
    grad = ImageChops.add(gv, gh, scale=2.0)
    img = ImageOps.colorize(grad, black=from_hex, white=to_hex).convert("RGBA")

    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=255)
    img.putalpha(mask)

    try:
        font = ImageFont.truetype("segoeuib.ttf", int(s * 0.62))
    except OSError:
        try:
            font = ImageFont.truetype("arialbd.ttf", int(s * 0.62))
        except OSError:
            font = ImageFont.load_default()

    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), "S", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (s - tw) / 2 - bbox[0]
    ty = (s - th) / 2 - bbox[1] - s * 0.02
    draw.text((tx, ty), "S", font=font, fill="white")

    return img.resize((64, 64), Image.LANCZOS)


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
        self._on_minimized_toggle: Optional[Callable] = None
        self._on_shutdown_toggle: Optional[Callable] = None
        self._on_shutdown_now: Optional[Callable] = None
        self._on_shutdown_postpone: Optional[Callable] = None
        self._on_shutdown_cancel: Optional[Callable] = None
        self._on_check_update: Optional[Callable] = None
        self._on_quit: Optional[Callable] = None

        self._is_paused = False
        self._auto_start = False
        self._current_time = "00:00:00"
        self._update_available = False
        self._update_version = ""
        self._shutdown_status = "desactivado"
        self._shutdown_enabled = False
        self._start_minimized = True

    def set_callbacks(self, **kwargs):
        self._on_show = kwargs.get("on_show")
        self._on_reset = kwargs.get("on_reset")
        self._on_pause_toggle = kwargs.get("on_pause_toggle")
        self._on_configure = kwargs.get("on_configure")
        self._on_autostart_toggle = kwargs.get("on_autostart_toggle")
        self._on_minimized_toggle = kwargs.get("on_minimized_toggle")
        self._on_shutdown_toggle = kwargs.get("on_shutdown_toggle")
        self._on_shutdown_now = kwargs.get("on_shutdown_now")
        self._on_shutdown_postpone = kwargs.get("on_shutdown_postpone")
        self._on_shutdown_cancel = kwargs.get("on_shutdown_cancel")
        self._on_check_update = kwargs.get("on_check_update")
        self._on_quit = kwargs.get("on_quit")

    def update_state(
        self,
        is_paused: bool,
        auto_start: bool,
        current_time: str,
        shutdown_status: str = "desactivado",
        shutdown_enabled: bool = False,
        start_minimized: bool = True,
    ):
        menu_changed = (
            self._is_paused != is_paused
            or self._auto_start != auto_start
            or self._start_minimized != start_minimized
            or self._shutdown_enabled != shutdown_enabled
        )
        self._is_paused = is_paused
        self._auto_start = auto_start
        self._current_time = current_time
        self._shutdown_status = shutdown_status
        self._shutdown_enabled = shutdown_enabled
        self._start_minimized = start_minimized
        if self._icon:
            status = "PAUSADO" if is_paused else "Activo"
            title = f"{get_app_name()} — {status} — {current_time}"
            if self._shutdown_enabled and self._shutdown_status != "desactivado":
                title += f" — ⏻ {self._shutdown_status}"
            self._icon.title = title
            if menu_changed:
                self._icon.menu = self._build_menu()

    def set_update_available(self, version: str):
        self._update_available = True
        self._update_version = version
        if self._icon:
            self._icon.menu = self._build_menu()

    def _build_menu(self) -> pystray.Menu:
        pause_text = "▶ Reanudar" if self._is_paused else "⏸ Pausar"
        autostart_text = "✓ Iniciar con Windows" if self._auto_start else "  Iniciar con Windows"
        minimized_text = "✓ Iniciar minimizado" if self._start_minimized else "  Iniciar minimizado"
        if self._shutdown_enabled:
            shutdown_text = "⏻ Desactivar apagado programado"
        else:
            shutdown_text = "⏻ Activar apagado automático"

        if self._update_available:
            update_text = f"⬆ Actualizar a {self._update_version}"
            update_item = pystray.MenuItem(
                update_text,
                lambda: self._safe_call(self._on_check_update),
            )
        else:
            update_item = pystray.MenuItem(
                " Buscar actualizaciones",
                lambda: self._safe_call(self._on_check_update),
            )

        shutdown_items = [
            pystray.MenuItem(
                shutdown_text,
                lambda: self._safe_call(self._on_shutdown_toggle),
            ),
            pystray.MenuItem(
                "⏻ Apagar ahora (60 s)",
                lambda: self._safe_call(self._on_shutdown_now),
            ),
        ]
        if self._shutdown_enabled:
            shutdown_items.append(
                pystray.MenuItem(
                    f"⏱ Posponer apagado ({DEFAULT_POSTPONE_MINUTES} min)",
                    lambda: self._safe_call(self._on_shutdown_postpone),
                )
            )
        shutdown_items.append(
            pystray.MenuItem(
                "✖ Cancelar apagado",
                lambda: self._safe_call(self._on_shutdown_cancel),
            )
        )

        return pystray.Menu(
            pystray.MenuItem(
                "📊 Ver tiempo actual",
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
            *shutdown_items,
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "⚙ Configurar intervalo",
                lambda: self._safe_call(self._on_configure),
            ),
            pystray.MenuItem(
                autostart_text,
                lambda: self._safe_call(self._on_autostart_toggle),
            ),
            pystray.MenuItem(
                minimized_text,
                lambda: self._safe_call(self._on_minimized_toggle),
            ),
            pystray.Menu.SEPARATOR,
            update_item,
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
