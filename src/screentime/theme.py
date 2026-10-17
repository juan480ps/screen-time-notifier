"""Design tokens: colores, tipografía, espaciado y utilidades de scroll."""

# ─── Paleta (tema oscuro moderno) ───────────────────────────────────────────
COLORS = {
    # Superficies
    "bg_dark": "#0B0F14",
    "bg_panel": "#141A22",
    "bg_card": "#1A222D",
    "surface": "#151B24",
    "surface_2": "#1E2733",
    "surface_3": "#27303D",
    "border": "#2A3543",
    "border_soft": "#212B37",
    # Acentos
    "accent_green": "#22C55E",
    "accent_green_light": "#4ADE80",
    "accent_neon": "#34D399",
    "accent_blue": "#0EA5E9",
    "accent_cyan": "#06B6D4",
    "accent": "#22C55E",
    # Texto
    "text_primary": "#E6EDF3",
    "text_secondary": "#93A1B0",
    "text_muted": "#5C6B7A",
    "text_warning": "#F59E0B",
    "text_danger": "#F85149",
    "on_accent": "#04140A",
    # Progreso / estados
    "progress_bg": "#27303D",
    "progress_fill": "#22C55E",
    "progress_warning": "#F59E0B",
    "progress_danger": "#F85149",
    "track_off": "#39434F",
    "success": "#22C55E",
    "warning": "#F59E0B",
    "danger": "#F85149",
}

FONT_FAMILY = "Segoe UI"
MONO_FAMILY = "Cascadia Mono"

FONTS = {
    "title": (FONT_FAMILY, 18, "bold"),
    "subtitle": (FONT_FAMILY, 9),
    "section": (FONT_FAMILY, 10, "bold"),
    "card_title": (FONT_FAMILY, 11, "bold"),
    "body": (FONT_FAMILY, 10),
    "body_bold": (FONT_FAMILY, 10, "bold"),
    "small": (FONT_FAMILY, 9),
    "tiny": (FONT_FAMILY, 8),
    "stat": (FONT_FAMILY, 15, "bold"),
    "clock": (MONO_FAMILY, 34, "bold"),
    "clock_sm": (MONO_FAMILY, 15, "bold"),
}

SPACING = {"xs": 4, "sm": 6, "md": 10, "lg": 14, "xl": 20}
RADIUS = 14

# ─── Scroll con rueda / trackpad ─────────────────────────────────────────────
SCROLL_PIXELS_PER_NOTCH = 50
SCROLL_MIN_STEP = 3


def unpack_touchpad_delta(value: int):
    """Decodifica Δx/Δy del evento <TouchpadScroll> de Tk 9.0.

    El delta llega como un entero de 32 bits con Δx en los 16 bits altos y Δy
    en los 16 bits bajos, ambos con signo (TIP 684). Puede venir como valor
    negativo o envuelto; se normaliza a 16 bits con signo en ambos casos.
    """
    dx = (value >> 16) & 0xFFFF
    dy = value & 0xFFFF
    if dx >= 0x8000:
        dx -= 0x10000
    if dy >= 0x8000:
        dy -= 0x10000
    return dx, dy


# ─── Modos de apagado automático ────────────────────────────────────────────
SHUTDOWN_MODE_KEYS = {"Hora fija": "hora", "Cuenta atrás": "temporizador"}
SHUTDOWN_MODE_LABELS = {value: key for key, value in SHUTDOWN_MODE_KEYS.items()}
