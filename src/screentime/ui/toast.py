"""Notificación estilo logro de Xbox, con animación de entrada/salida."""

import time
import tkinter as tk

from screentime.theme import COLORS, FONTS
from screentime.ui.widgets import round_rect

WIDTH = 400
HEIGHT = 100
MARGIN = 16
GAP = 10

_IN_FRAMES = 18
_OUT_FRAMES = 12
_FRAME_MS = 15


class AchievementToast:
    """Toast individual apilable, tipo 'Logro desbloqueado'."""

    _active = []

    def __init__(self, master, message, duration_ms=8000, title="SCREEN TIME"):
        self.master = master
        self.duration = max(1500.0, float(duration_ms))
        self.message = message
        self.title = title
        self._closing = False
        self._out_job = None
        self._tick_job = None

        self.tl = tk.Toplevel(master)
        self.tl.overrideredirect(True)
        self.tl.attributes("-topmost", True)
        self.tl.attributes("-alpha", 0.0)
        self.tl.configure(bg=COLORS["bg_dark"])

        self.screen_w = self.tl.winfo_screenwidth()
        self.target_x = self.screen_w - WIDTH - MARGIN
        self.base_y = MARGIN + len(AchievementToast._active) * (HEIGHT + GAP)
        self.start_x = self.screen_w + 10

        self.canvas = tk.Canvas(
            self.tl, width=WIDTH, height=HEIGHT, bg=COLORS["bg_dark"], highlightthickness=0,
        )
        self.canvas.pack()
        self._draw()
        self.tl.geometry(f"{WIDTH}x{HEIGHT}+{self.start_x}+{self.base_y}")
        self.tl.bind("<Button-1>", lambda e: self.dismiss())

        AchievementToast._active.append(self)
        self._animate_in(0)

    # ─── Dibujo ──────────────────────────────────────────────────────────

    def _draw(self):
        c = self.canvas
        c.delete("all")
        round_rect(c, 1, 1, WIDTH - 1, HEIGHT - 1, 18, fill=COLORS["surface"], outline=COLORS["accent"])
        round_rect(c, 2, 2, WIDTH - 2, HEIGHT - 2, 17, fill=COLORS["surface"], outline="")

        # Icono: reloj (tiempo en pantalla)
        cx, cy, r = 46, HEIGHT // 2, 24
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=COLORS["accent"], outline="")
        fr = 12
        c.create_oval(cx - fr, cy - fr, cx + fr, cy + fr, outline="white", width=2)
        c.create_line(cx, cy, cx, cy - 7, fill="white", width=2)
        c.create_line(cx, cy, cx + 6, cy + 3, fill="white", width=2)
        c.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill="white", outline="")

        # Textos
        c.create_text(82, 32, text=self.title, anchor="w", fill=COLORS["text_muted"],
                      font=(FONTS["tiny"][0], 8, "bold"))
        c.create_text(82, 54, text=self.message, anchor="nw", fill=COLORS["text_primary"],
                      font=(FONTS["body"][0], 10, "bold"), width=WIDTH - 106, justify="left")

        # Barra de progreso (duración)
        self._bar = c.create_rectangle(2, HEIGHT - 6, WIDTH - 2, HEIGHT - 2,
                                       fill=COLORS["accent"], outline="")

    def _set_bar(self, fraction):
        self.canvas.coords(self._bar, 2, HEIGHT - 6, int(2 + (WIDTH - 4) * fraction), HEIGHT - 2)

    # ─── Animación ───────────────────────────────────────────────────────

    def _animate_in(self, step):
        if not self.tl.winfo_exists():
            return
        t = step / _IN_FRAMES
        ease = 1 - (1 - t) ** 3
        x = int(self.start_x + (self.target_x - self.start_x) * ease)
        self.tl.geometry(f"{WIDTH}x{HEIGHT}+{x}+{self.base_y}")
        self.tl.attributes("-alpha", min(1.0, 0.35 + 0.65 * ease))
        if step < _IN_FRAMES:
            self.tl.after(_FRAME_MS, lambda: self._animate_in(step + 1))
        else:
            self.tl.attributes("-alpha", 1.0)
            self._begin_countdown()

    def _begin_countdown(self):
        self._start = time.monotonic()
        self._tick()

    def _tick(self):
        if self._closing or not self.tl.winfo_exists():
            return
        elapsed = (time.monotonic() - self._start) * 1000.0
        remain = self.duration - elapsed
        self._set_bar(max(0.0, remain / self.duration))
        if remain <= 0:
            self.dismiss()
        else:
            self._tick_job = self.tl.after(50, self._tick)

    def dismiss(self):
        if self._closing:
            return
        self._closing = True
        for job in (self._out_job, self._tick_job):
            if job:
                try:
                    self.tl.after_cancel(job)
                except tk.TclError:
                    pass
        self._animate_out(0)

    def _animate_out(self, step):
        if not self.tl.winfo_exists():
            return
        t = step / _OUT_FRAMES
        ease = t * t
        x = int(self.target_x + (self.screen_w + 20 - self.target_x) * ease)
        self.tl.geometry(f"{WIDTH}x{HEIGHT}+{x}+{self.base_y}")
        self.tl.attributes("-alpha", max(0.0, 1.0 - t))
        if step < _OUT_FRAMES:
            self.tl.after(_FRAME_MS, lambda: self._animate_out(step + 1))
        else:
            self._destroy()

    def _destroy(self):
        if self in AchievementToast._active:
            AchievementToast._active.remove(self)
        try:
            self.tl.destroy()
        except tk.TclError:
            pass
        self._restack()

    @staticmethod
    def _restack():
        for i, toast in enumerate(AchievementToast._active):
            toast.base_y = MARGIN + i * (HEIGHT + GAP)
            try:
                if toast.tl.winfo_exists():
                    toast.tl.geometry(f"+{toast.target_x}+{toast.base_y}")
            except tk.TclError:
                pass


def show_achievement(master, message, duration_seconds=8.0):
    """Muestra un toast animado estilo logro. Seguro ante master inválido."""
    if master is None:
        return
    try:
        AchievementToast(master, message, duration_ms=int(duration_seconds * 1000))
    except tk.TclError:
        pass
