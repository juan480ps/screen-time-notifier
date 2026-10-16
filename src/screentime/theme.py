"""Tema visual, colores y utilidades de scroll compartidas por la UI."""

# ─── Colores del tema Xbox/Gaming ───────────────────────────────────────────
COLORS = {
    "bg_dark": "#0e0e0e",
    "bg_panel": "#1a1a2e",
    "bg_card": "#16213e",
    "accent_green": "#107C10",
    "accent_green_light": "#1db954",
    "accent_blue": "#0f3460",
    "accent_neon": "#00ff88",
    "text_primary": "#e0e0e0",
    "text_secondary": "#a0a0a0",
    "text_warning": "#ff6b35",
    "text_danger": "#ff4444",
    "progress_bg": "#2a2a2a",
    "progress_fill": "#107C10",
    "progress_warning": "#ff6b35",
    "progress_danger": "#ff4444",
    "border": "#2a2a4a",
}

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
