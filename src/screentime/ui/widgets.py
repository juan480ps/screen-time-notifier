"""Widgets reutilizables (tkinter/Canvas) para una UI moderna."""

import tkinter as tk
from datetime import date

from screentime.theme import COLORS, FONTS, SPACING


def round_rect(canvas: tk.Canvas, x0, y0, x1, y1, r, **kwargs):
    """Dibuja un rectángulo redondeado usando un polygono suavizado."""
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    pts = [
        x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
        x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
        x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
    ]
    return canvas.create_polygon(pts, smooth=True, **kwargs)


def make_button(parent, text, command=None, kind="primary", width=None, pad=(14, 7)):
    """Botón plano con variantes de color."""
    palettes = {
        "primary": (COLORS["accent"], COLORS["on_accent"]),
        "ghost": (COLORS["surface_3"], COLORS["text_primary"]),
        "danger": (COLORS["danger"], "#FFFFFF"),
        "warning": (COLORS["warning"], "#1A1200"),
    }
    bg, fg = palettes.get(kind, palettes["primary"])
    return tk.Button(
        parent, text=text, command=command, font=FONTS["small"],
        bg=bg, fg=fg, activebackground=bg, activeforeground=fg,
        relief="flat", bd=0, highlightthickness=0, cursor="hand2",
        padx=pad[0], pady=pad[1], width=width,
    )


class Card(tk.Frame):
    """Panel con borde sutil y padding; expone `.body` para el contenido."""

    def __init__(self, master, title=None, pad=12, **kw):
        super().__init__(
            master, bg=COLORS["surface"], highlightbackground=COLORS["border"],
            highlightthickness=1, bd=0, **kw,
        )
        self.body = tk.Frame(self, bg=COLORS["surface"])
        if title:
            tk.Label(
                self, text=title, font=FONTS["section"], fg=COLORS["text_secondary"],
                bg=COLORS["surface"], anchor="w",
            ).pack(fill=tk.X, padx=pad, pady=(pad, 0))
            self.body.pack(fill=tk.BOTH, expand=True, padx=pad, pady=(SPACING["sm"], pad))
        else:
            self.body.pack(fill=tk.BOTH, expand=True, padx=pad, pady=pad)


class ToggleSwitch(tk.Canvas):
    """Interruptor moderno ligado a un BooleanVar."""

    def __init__(self, master, variable, command=None, width=48, height=26, **kw):
        super().__init__(
            master, width=width, height=height, highlightthickness=0, bd=0,
            bg=kw.pop("bg", COLORS["surface"]), **kw,
        )
        self._var = variable
        self._command = command
        self._cw, self._ch = width, height
        self._enabled = True
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._on_click)
        self._var.trace_add("write", lambda *_: self._draw())
        self._draw()

    def set_enabled(self, enabled: bool):
        self._enabled = bool(enabled)
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def _on_click(self, _event=None):
        if not self._enabled:
            return
        self._var.set(not self._var.get())
        if self._command:
            self._command(self._var.get())

    def _draw(self):
        self.delete("all")
        on = bool(self._var.get())
        pad = 3
        x0, y0, x1, y1 = pad, pad, self._cw - pad, self._ch - pad
        r = (y1 - y0) / 2
        if not self._enabled:
            track = COLORS["surface_3"]
        else:
            track = COLORS["accent"] if on else COLORS["track_off"]
        round_rect(self, x0, y0, x1, y1, r, fill=track, outline="")
        knob = (y1 - y0) - 2
        kx = (x1 - r - 1) if on else (x0 + r + 1)
        ky = (y0 + y1) / 2
        if not self._enabled:
            fill = COLORS["text_muted"]
        else:
            fill = "white" if on else "#C7CED6"
        self.create_oval(kx - knob / 2, ky - knob / 2, kx + knob / 2, ky + knob / 2,
                         fill=fill, outline="")


class BarProgress(tk.Canvas):
    """Barra de progreso redondeada con texto opcional."""

    def __init__(self, master, height=18, **kw):
        super().__init__(
            master, height=height, highlightthickness=0, bd=0,
            bg=kw.pop("bg", COLORS["surface"]), **kw,
        )
        self._h = height
        self._fraction = 0.0
        self._color = COLORS["progress_fill"]
        self._text = ""
        self._text_color = COLORS["text_primary"]
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, fraction, color=None, text="", text_color=None):
        self._fraction = max(0.0, min(1.0, fraction))
        self._color = color or COLORS["progress_fill"]
        self._text = text
        self._text_color = text_color or COLORS["text_primary"]
        self._draw()

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self._h
        if w <= 1:
            return
        r = h / 2
        round_rect(self, 0, 1, w, h - 1, r, fill=COLORS["progress_bg"], outline="")
        fw = int(w * self._fraction)
        if fw > 0:
            round_rect(self, 0, 1, max(fw, h), h - 1, r, fill=self._color, outline="")
        if self._text:
            self.create_text(w / 2, h / 2, text=self._text, fill=self._text_color,
                             font=FONTS["tiny"])


class RingProgress(tk.Canvas):
    """Anillo de progreso con texto central."""

    def __init__(self, master, size=190, thickness=14, **kw):
        super().__init__(
            master, width=size, height=size, highlightthickness=0, bd=0,
            bg=kw.pop("bg", COLORS["surface"]), **kw,
        )
        self._size = size
        self._th = thickness
        self._frac = 0.0
        self._color = COLORS["accent"]
        self._main = ""
        self._sub = ""

    def set(self, fraction, color=None, main="", sub=""):
        self._frac = max(0.0, min(1.0, fraction))
        self._color = color or COLORS["accent"]
        self._main = main
        self._sub = sub
        self._draw()

    def _draw(self):
        self.delete("all")
        s, th = self._size, self._th
        m = th / 2 + 2
        self.create_oval(m, m, s - m, s - m, outline=COLORS["progress_bg"], width=th)
        if self._frac >= 0.999:
            self.create_oval(m, m, s - m, s - m, outline=self._color, width=th)
        elif self._frac > 0:
            self.create_arc(m, m, s - m, s - m, start=90, extent=-359.9 * self._frac,
                            style="arc", outline=self._color, width=th)
        main_size = max(12, int(s * 0.13))
        self.create_text(s / 2, s / 2 - 4, text=self._main, fill=COLORS["text_primary"],
                         font=(FONTS["clock"][0], main_size, "bold"))
        if self._sub:
            self.create_text(s / 2, s / 2 + main_size + 4, text=self._sub,
                             fill=COLORS["text_secondary"], font=FONTS["small"])


class StatTile(tk.Frame):
    """Tarjeta compacta de estadística."""

    def __init__(self, master, label, value_var, value_color=COLORS["text_primary"], **kw):
        super().__init__(
            master, bg=COLORS["surface_2"], highlightbackground=COLORS["border_soft"],
            highlightthickness=1, bd=0, **kw,
        )
        tk.Label(self, textvariable=value_var, font=FONTS["stat"], fg=value_color,
                 bg=COLORS["surface_2"]).pack(pady=(6, 0))
        tk.Label(self, text=label, font=FONTS["tiny"], fg=COLORS["text_secondary"],
                 bg=COLORS["surface_2"]).pack(pady=(0, 6))


class WeekChart(tk.Canvas):
    """Gráfico de barras de actividad semanal."""

    def __init__(self, master, height=64, **kw):
        super().__init__(
            master, height=height, highlightthickness=0, bd=0,
            bg=kw.pop("bg", COLORS["surface"]), **kw,
        )
        self._h = height
        self._data = []
        self.bind("<Configure>", lambda e: self._draw())

    def render(self, week_stats: dict):
        self._data = list(reversed(list(week_stats.items())))
        self._draw()

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self._h
        if w <= 1 or not self._data:
            return
        n = len(self._data)
        gap = 8
        bar_w = max(12, (w - gap * (n + 1)) // n)
        max_val = max((v for _, v in self._data), default=0) or 1
        names = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        for i, (day_str, seconds) in enumerate(self._data):
            x = gap + i * (bar_w + gap)
            bh = max(3, int((seconds / max_val) * (h - 26)))
            y1 = h - 16
            y0 = y1 - bh
            color = COLORS["accent"] if seconds > 0 else COLORS["surface_3"]
            round_rect(self, x, y0, x + bar_w, y1, min(6, bar_w / 2), fill=color, outline="")
            try:
                label = names[date.fromisoformat(day_str).weekday()]
            except (ValueError, IndexError):
                label = day_str[-2:]
            self.create_text(x + bar_w / 2, h - 6, text=label, fill=COLORS["text_secondary"],
                             font=FONTS["tiny"])
