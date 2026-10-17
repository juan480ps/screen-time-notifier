"""Panel in-app de recursos (CPU/RAM/GPU) con histórico tipo sparkline."""

from __future__ import annotations

import tkinter as tk
from typing import Any, Iterable, List

from screentime.theme import COLORS, FONTS, SPACING
from screentime.ui.widgets import BarProgress, Card

_METRICS = (
    ("cpu", "CPU", COLORS["accent"]),
    ("ram", "RAM", COLORS["accent_blue"]),
    ("gpu", "GPU", COLORS["warning"]),
)


class ResourcePanel(Card):
    """Tarjeta compacta: 3 gauges + gráfico de líneas en tiempo real."""

    def __init__(self, master, capacity: int = 60, **kw):
        super().__init__(master, title="RECURSOS", **kw)
        self._capacity = max(10, int(capacity))
        self._history: List[Any] = []
        self._values = {}
        self._bars = {}

        row = tk.Frame(self.body, bg=COLORS["surface"])
        row.pack(fill=tk.X)
        for i, (key, label, color) in enumerate(_METRICS):
            col = tk.Frame(row, bg=COLORS["surface_2"], padx=8, pady=6)
            col.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0 if i == 0 else 6, 0))
            tk.Label(col, text=label, font=FONTS["tiny"], fg=COLORS["text_secondary"],
                     bg=COLORS["surface_2"]).pack(anchor="w")
            var = tk.StringVar(value="--")
            self._values[key] = var
            tk.Label(col, textvariable=var, font=FONTS["stat"], fg=color,
                     bg=COLORS["surface_2"]).pack(anchor="w")
            bar = BarProgress(col, height=6, width=1, bg=COLORS["surface_2"])
            bar.pack(fill=tk.X, pady=(SPACING["xs"], 0))
            self._bars[key] = bar

        self._chart = tk.Canvas(self.body, height=46, width=1, bg=COLORS["surface"],
                                highlightthickness=0, bd=0)
        self._chart.pack(fill=tk.BOTH, expand=True, pady=(SPACING["sm"], 0))
        self._chart.bind("<Configure>", lambda e: self._draw())
        self.update_history([])

    def update_history(self, history: Iterable[Any]) -> None:
        items = list(history)[-self._capacity:]
        self._history = items
        last = items[-1] if items else None
        for key, _label, color in _METRICS:
            value = getattr(last, key, None) if last is not None else None
            self._values[key].set("N/D" if value is None else f"{value:.0f}%")
            frac = 0.0 if value is None else min(1.0, max(0.0, float(value) / 100.0))
            self._bars[key].set(frac, color if value is not None else COLORS["surface_3"])
        self._draw()

    def _draw(self) -> None:
        c = self._chart
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w <= 1:
            return
        c.create_line(1, h / 2, w - 1, h / 2, fill=COLORS["border_soft"])
        items = self._history
        if len(items) < 2:
            return
        span = max(self._capacity - 1, 1)
        for key, _label, color in _METRICS:
            points = []
            for i, snap in enumerate(items):
                value = getattr(snap, key, None)
                if value is None:
                    continue
                x = 1 + (w - 2) * i / span
                y = 2 + (h - 4) * (1 - min(100.0, max(0.0, float(value))) / 100.0)
                points.extend((x, y))
            if len(points) >= 4:
                c.create_line(*points, fill=color, width=2)
