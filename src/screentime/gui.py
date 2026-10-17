"""Interfaz gráfica principal de la aplicación."""

import tkinter as tk
from typing import Optional

from screentime.config import ICON_PATH, get_app_name, get_app_version
from screentime.shutdown import DEFAULT_POSTPONE_MINUTES
from screentime.theme import (
    COLORS,
    FONTS,
    SCROLL_MIN_STEP,
    SCROLL_PIXELS_PER_NOTCH,
    SHUTDOWN_MODE_KEYS,
    SHUTDOWN_MODE_LABELS,
    SPACING,
    unpack_touchpad_delta,
)
from screentime.ui.widgets import (
    BarProgress,
    Card,
    RingProgress,
    StatTile,
    ToggleSwitch,
    WeekChart,
    make_button,
)


class MainGUI:
    """Ventana principal con diseño moderno y modular."""

    def __init__(self, logger, notifier, settings: dict = None):
        self.logger = logger
        self.notifier = notifier
        self.settings = settings or {}
        self.root: Optional[tk.Tk] = None
        self._update_job = None
        self._visible = False
        self._wheel_delta = 0.0

        self.time_var = None
        self.status_var = None
        self.today_total_var = None
        self.sessions_var = None
        self.session_var = None
        self.interval_val_var = None
        self.interval_unit_var = None
        self.overlay_var = None
        self.pomodoro_state_var = None
        self.pomodoro_timer_var = None
        self.pomodoro_cycle_var = None
        self.daily_goal_var = None
        self.daily_goal_hours_var = None
        self.lock_val_var = None
        self.lock_unit_var = None
        self.shutdown_mode_var = None
        self.shutdown_hour_var = None
        self.shutdown_minute_var = None
        self.shutdown_minutes_var = None
        self.shutdown_unit_var = None
        self.shutdown_warn_var = None
        self.shutdown_status_var = None
        self.daily_goal_enabled = None
        self.pomodoro_enabled = None
        self.game_mode_enabled = None
        self.screen_lock_enabled = None
        self.shutdown_enabled = None
        self.auto_start_var = None
        self.start_minimized_var = None
        self.game_status_dot = None

        self._on_interval_change = None
        self._on_overlay_change = None
        self._on_pomodoro_start = None
        self._on_pomodoro_stop = None
        self._on_pomodoro_skip = None
        self._on_export_csv = None
        self._on_daily_goal_toggle = None
        self._on_daily_goal_change = None
        self._on_pomodoro_toggle = None
        self._on_game_mode_toggle = None
        self._on_screen_lock_toggle = None
        self._on_screen_lock_change = None
        self._on_shutdown_change = None
        self._on_shutdown_now = None
        self._on_shutdown_postpone = None
        self._on_shutdown_cancel = None
        self._on_autostart_toggle = None
        self._on_start_minimized_toggle = None

        self._suppress_callbacks = False
        self._shutdown_emit_job = None
        self._daily_goal_hours = 8

    # ─── Ventana ─────────────────────────────────────────────────────────

    def create_window(self, start_minimized: bool = False) -> tk.Tk:
        if self.root is not None:
            self.root.deiconify()
            self.root.lift()
            self._visible = True
            return self.root

        self.root = tk.Tk()
        if start_minimized:
            self.root.withdraw()

        self._create_vars()
        self.root.title(f"{get_app_name()} v{get_app_version()}")
        self.root.minsize(820, 500)
        self.root.configure(bg=COLORS["bg_dark"])
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        try:
            from PIL import Image, ImageTk
            with Image.open(ICON_PATH) as img:
                photo = ImageTk.PhotoImage(img)
            self.root.iconphoto(True, photo)
            self._icon_photo = photo
        except Exception:
            try:
                self.root.iconbitmap(ICON_PATH)
            except Exception:
                pass

        saved_geo = self.settings.get("window_geometry")
        used_saved_geo = False
        if saved_geo:
            try:
                self.root.geometry(saved_geo)
                used_saved_geo = True
            except Exception:
                used_saved_geo = False
        if not used_saved_geo:
            self.root.geometry("1160x680")
            if not start_minimized:
                self._center_window()

        self._build_ui()
        self._start_update_loop()
        self._visible = not start_minimized
        return self.root

    def _create_vars(self):
        self.time_var = tk.StringVar(value="00:00:00")
        self.status_var = tk.StringVar(value="Activo")
        self.today_total_var = tk.StringVar(value="0h 00m")
        self.sessions_var = tk.StringVar(value="0")
        self.session_var = tk.StringVar(value="0h 00m")
        self.interval_val_var = tk.StringVar(value="30")
        self.interval_unit_var = tk.StringVar(value="Minutos")
        self.overlay_var = tk.StringVar(value="8")
        self.pomodoro_state_var = tk.StringVar(value="Inactivo")
        self.pomodoro_timer_var = tk.StringVar(value="00:00")
        self.pomodoro_cycle_var = tk.StringVar(value="0/4")
        self.daily_goal_var = tk.StringVar(value="0h 00m / 8h")
        self.daily_goal_hours_var = tk.StringVar(value="8")
        self.lock_val_var = tk.StringVar(value="4")
        self.lock_unit_var = tk.StringVar(value="Horas")
        self.shutdown_mode_var = tk.StringVar(value="Hora fija")
        self.shutdown_hour_var = tk.StringVar(value="23")
        self.shutdown_minute_var = tk.StringVar(value="00")
        self.shutdown_minutes_var = tk.StringVar(value="60")
        self.shutdown_unit_var = tk.StringVar(value="Minutos")
        self.shutdown_warn_var = tk.StringVar(value="5")
        self.shutdown_status_var = tk.StringVar(value="Desactivado")
        self.daily_goal_enabled = tk.BooleanVar(value=False)
        self.pomodoro_enabled = tk.BooleanVar(value=False)
        self.game_mode_enabled = tk.BooleanVar(value=False)
        self.screen_lock_enabled = tk.BooleanVar(value=False)
        self.shutdown_enabled = tk.BooleanVar(value=False)
        self.auto_start_var = tk.BooleanVar(value=False)
        self.start_minimized_var = tk.BooleanVar(value=True)

    # ─── Construcción de UI ──────────────────────────────────────────────

    def _build_ui(self):
        self._canvas = tk.Canvas(
            self.root, bg=COLORS["bg_dark"], highlightthickness=0, yscrollincrement=1,
        )
        self._scrollbar = tk.Scrollbar(self.root, orient="vertical", command=self._canvas.yview)
        self._scroll_frame = tk.Frame(self._canvas, bg=COLORS["bg_dark"])
        self._scroll_frame.bind("<Configure>", self._on_content_configure)
        self._canvas_window = self._canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        try:
            self._canvas.bind_all("<TouchpadScroll>", self._on_touchpad_scroll)
        except tk.TclError:
            pass

        content = tk.Frame(self._scroll_frame, bg=COLORS["bg_dark"])
        content.pack(fill=tk.X, padx=18, pady=(10, 16))

        self._build_header(content)

        cols = tk.Frame(content, bg=COLORS["bg_dark"])
        cols.pack(fill=tk.BOTH, expand=True)
        for c in range(3):
            cols.columnconfigure(c, weight=1, uniform="col")

        left = tk.Frame(cols, bg=COLORS["bg_dark"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        mid = tk.Frame(cols, bg=COLORS["bg_dark"])
        mid.grid(row=0, column=1, sticky="nsew", padx=8)
        right = tk.Frame(cols, bg=COLORS["bg_dark"])
        right.grid(row=0, column=2, sticky="nsew", padx=(8, 0))

        self._section(left, "RESUMEN")
        self._build_hero(left)
        self._build_stats(left)
        self._build_weekly(left)

        self._section(mid, "ENFOQUE")
        self._build_config(mid)
        self._card_meta(mid)
        self._card_pomodoro(mid)
        self._card_game(mid)

        self._section(right, "BIENESTAR")
        self._card_lock(right)
        self._build_shutdown(right)
        self._build_startup(right)

        self._build_footer(content)
        self._update_shutdown_widgets()
        self.root.after(60, self._update_scroll_state)

    def _build_header(self, parent):
        header = tk.Frame(parent, bg=COLORS["bg_dark"])
        header.pack(fill=tk.X, pady=(6, 10))
        left = tk.Frame(header, bg=COLORS["bg_dark"])
        left.pack(side=tk.LEFT)
        tk.Label(left, text="SCREEN TIME", font=FONTS["title"], fg=COLORS["text_primary"],
                 bg=COLORS["bg_dark"]).pack(anchor="w")
        tk.Label(left, text="Monitor de tiempo en pantalla", font=FONTS["subtitle"],
                 fg=COLORS["text_secondary"], bg=COLORS["bg_dark"]).pack(anchor="w")
        self.status_pill = tk.Label(
            header, textvariable=self.status_var, font=FONTS["small"],
            fg=COLORS["accent_green_light"], bg=COLORS["surface_2"], padx=12, pady=5,
        )
        self.status_pill.pack(side=tk.RIGHT, pady=(4, 0))

    def _build_hero(self, parent):
        card = Card(parent)
        card.pack(fill=tk.X, pady=(0, SPACING["md"]))
        self.ring = RingProgress(card.body, size=140, thickness=12)
        self.ring.pack(pady=(SPACING["sm"], SPACING["md"]))
        tk.Label(card.body, text="PROGRESO DE SESIÓN", font=FONTS["tiny"],
                 fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(anchor="w")
        self.progress_bar = BarProgress(card.body, height=16)
        self.progress_bar.pack(fill=tk.X, pady=(SPACING["xs"], 0))

    def _build_stats(self, parent):
        row = tk.Frame(parent, bg=COLORS["bg_dark"])
        row.pack(fill=tk.X, pady=(0, SPACING["md"]))
        for i, (label, var, color) in enumerate((
            ("Total hoy", self.today_total_var, COLORS["accent_neon"]),
            ("Sesiones", self.sessions_var, COLORS["accent_green_light"]),
            ("Sesión actual", self.session_var, COLORS["text_primary"]),
        )):
            tile = StatTile(row, label, var, color)
            tile.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0 if i == 0 else 6, 0))

    def _build_config(self, parent):
        card = Card(parent, title="CONFIGURACIÓN")
        card.pack(fill=tk.X, pady=(0, SPACING["md"]))
        row = tk.Frame(card.body, bg=COLORS["surface"])
        row.pack(fill=tk.X)
        tk.Label(row, text="Aviso cada", font=FONTS["body"], fg=COLORS["text_secondary"],
                 bg=COLORS["surface"]).pack(side=tk.LEFT)
        self.interval_spinner = self._spinbox(row, self.interval_val_var, 1, 120, width=4)
        self.interval_spinner.pack(side=tk.LEFT, padx=(8, 6))
        self.interval_unit_menu = self._option_menu(row, self.interval_unit_var,
                                                    ("Segundos", "Minutos", "Horas"), width=9)
        self.interval_unit_menu.pack(side=tk.LEFT)
        make_button(row, "Aplicar", self._on_apply_interval, kind="primary").pack(side=tk.LEFT, padx=(8, 0))

        row2 = tk.Frame(card.body, bg=COLORS["surface"])
        row2.pack(fill=tk.X, pady=(SPACING["md"], 0))
        tk.Label(row2, text="Popup visible", font=FONTS["body"], fg=COLORS["text_secondary"],
                 bg=COLORS["surface"]).pack(side=tk.LEFT)
        self.overlay_spinner = self._spinbox(row2, self.overlay_var, 2, 30, width=3)
        self.overlay_spinner.pack(side=tk.LEFT, padx=(8, 6))
        tk.Label(row2, text="segundos", font=FONTS["small"], fg=COLORS["text_muted"],
                 bg=COLORS["surface"]).pack(side=tk.LEFT)
        self.interval_unit_var.trace_add("write", self._on_unit_change_inline)

    def _build_weekly(self, parent):
        card = Card(parent, title="ACTIVIDAD SEMANAL")
        card.pack(fill=tk.X, pady=(0, SPACING["md"]))
        self.week_chart = WeekChart(card.body, height=50)
        self.week_chart.pack(fill=tk.X)

    def _section(self, parent, text):
        tk.Label(parent, text=text, font=FONTS["section"], fg=COLORS["text_muted"],
                 bg=COLORS["bg_dark"]).pack(anchor="w", pady=(0, SPACING["sm"]))

    def _card_meta(self, parent):
        card = Card(parent)
        card.pack(fill=tk.X, pady=(0, SPACING["sm"]))
        self._toggle_row(card.body, "Meta diaria", self.daily_goal_enabled,
                         self._on_daily_goal_toggle_click)
        row = tk.Frame(card.body, bg=COLORS["surface"])
        row.pack(fill=tk.X, pady=(SPACING["sm"], 0))
        self.goal_hours_spinner = self._spinbox(row, self.daily_goal_hours_var, 1, 16, width=3)
        self.goal_hours_spinner.pack(side=tk.LEFT)
        tk.Label(row, text="horas máximo al día", font=FONTS["small"], fg=COLORS["text_secondary"],
                 bg=COLORS["surface"]).pack(side=tk.LEFT, padx=(8, 0))
        self.goal_bar = BarProgress(card.body, height=14)
        self.goal_bar.pack(fill=tk.X, pady=(SPACING["sm"], 0))
        self.daily_goal_hours_var.trace_add("write", self._on_goal_hours_change)

    def _card_pomodoro(self, parent):
        card = Card(parent)
        card.pack(fill=tk.X, pady=(0, SPACING["sm"]))
        self._toggle_row(card.body, "Pomodoro", self.pomodoro_enabled, self._on_pomodoro_toggle_click)
        info = tk.Frame(card.body, bg=COLORS["surface"])
        info.pack(fill=tk.X, pady=(SPACING["sm"], SPACING["sm"]))
        tk.Label(info, textvariable=self.pomodoro_state_var, font=FONTS["body"],
                 fg=COLORS["accent_green_light"], bg=COLORS["surface"]).pack(side=tk.LEFT)
        tk.Label(info, textvariable=self.pomodoro_timer_var, font=FONTS["clock_sm"],
                 fg=COLORS["text_primary"], bg=COLORS["surface"]).pack(side=tk.RIGHT)
        btns = tk.Frame(card.body, bg=COLORS["surface"])
        btns.pack(fill=tk.X)
        tk.Label(btns, textvariable=self.pomodoro_cycle_var, font=FONTS["tiny"],
                 fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(side=tk.LEFT)
        make_button(btns, "Iniciar", self._on_pomodoro_start_click, kind="primary",
                    pad=(10, 5)).pack(side=tk.RIGHT, padx=(6, 0))
        make_button(btns, "Saltar", self._on_pomodoro_skip_click, kind="ghost",
                    pad=(10, 5)).pack(side=tk.RIGHT, padx=(6, 0))
        make_button(btns, "Parar", self._on_pomodoro_stop_click, kind="danger",
                    pad=(10, 5)).pack(side=tk.RIGHT)

    def _card_game(self, parent):
        card = Card(parent)
        card.pack(fill=tk.X, pady=(0, SPACING["sm"]))
        self._toggle_row(card.body, "Modo juego", self.game_mode_enabled,
                         self._on_game_mode_toggle_click, right_factory=self._make_game_dot)

    def _card_lock(self, parent):
        card = Card(parent)
        card.pack(fill=tk.X, pady=(0, SPACING["sm"]))
        self._toggle_row(card.body, "Bloqueo de pantalla", self.screen_lock_enabled,
                         self._on_screen_lock_toggle_click)
        row = tk.Frame(card.body, bg=COLORS["surface"])
        row.pack(fill=tk.X, pady=(SPACING["sm"], 0))
        tk.Label(row, text="Bloquear después de", font=FONTS["small"], fg=COLORS["text_secondary"],
                 bg=COLORS["surface"]).pack(side=tk.LEFT)
        self.lock_val_spinner = self._spinbox(row, self.lock_val_var, 1, 12, width=3)
        self.lock_val_spinner.pack(side=tk.LEFT, padx=(8, 6))
        self.lock_unit_menu = self._option_menu(row, self.lock_unit_var, ("Minutos", "Horas"), width=8)
        self.lock_unit_menu.pack(side=tk.LEFT)
        self.lock_val_var.trace_add("write", self._on_lock_change)
        self.lock_unit_var.trace_add("write", self._on_lock_unit_change)

    def _build_shutdown(self, parent):
        card = Card(parent)
        card.pack(fill=tk.X, pady=(0, SPACING["sm"]))
        self._toggle_row(card.body, "Apagado automático", self.shutdown_enabled,
                         self._on_shutdown_toggle_click)

        self.shutdown_status_label = tk.Label(
            card.body, textvariable=self.shutdown_status_var, font=FONTS["tiny"],
            fg=COLORS["accent_green_light"], bg=COLORS["surface"], anchor="w",
        )
        self.shutdown_status_label.pack(fill=tk.X, pady=(SPACING["sm"], 0))

        mode_row = tk.Frame(card.body, bg=COLORS["surface"])
        mode_row.pack(fill=tk.X, pady=(SPACING["sm"], 0))
        tk.Label(mode_row, text="Modo:", font=FONTS["small"], fg=COLORS["text_secondary"],
                 bg=COLORS["surface"]).pack(side=tk.LEFT)
        self.shutdown_mode_menu = self._option_menu(mode_row, self.shutdown_mode_var,
                                                    tuple(SHUTDOWN_MODE_KEYS.keys()), width=12)
        self.shutdown_mode_menu.pack(side=tk.LEFT, padx=(8, 0))

        self.shutdown_time_row = tk.Frame(card.body, bg=COLORS["surface"])
        self.shutdown_time_row.pack(fill=tk.X, pady=(SPACING["sm"], 0))
        tk.Label(self.shutdown_time_row, text="Apagar a las", font=FONTS["small"],
                 fg=COLORS["text_secondary"], bg=COLORS["surface"]).pack(side=tk.LEFT)
        self.shutdown_hour_spinner = self._spinbox(self.shutdown_time_row, self.shutdown_hour_var, 0, 23, width=3)
        self.shutdown_hour_spinner.pack(side=tk.LEFT, padx=(8, 2))
        tk.Label(self.shutdown_time_row, text=":", font=FONTS["body_bold"], fg=COLORS["text_secondary"],
                 bg=COLORS["surface"]).pack(side=tk.LEFT)
        self.shutdown_minute_spinner = self._spinbox(self.shutdown_time_row, self.shutdown_minute_var, 0, 59, width=3)
        self.shutdown_minute_spinner.pack(side=tk.LEFT, padx=(2, 6))
        tk.Label(self.shutdown_time_row, text="(cada día)", font=FONTS["tiny"],
                 fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(side=tk.LEFT)

        self.shutdown_countdown_row = tk.Frame(card.body, bg=COLORS["surface"])
        self.shutdown_countdown_row.pack(fill=tk.X, pady=(SPACING["sm"], 0))
        tk.Label(self.shutdown_countdown_row, text="Apagar en", font=FONTS["small"],
                 fg=COLORS["text_secondary"], bg=COLORS["surface"]).pack(side=tk.LEFT)
        self.shutdown_minutes_spinner = self._spinbox(
            self.shutdown_countdown_row, self.shutdown_minutes_var, 1, 720, width=4,
        )
        self.shutdown_minutes_spinner.pack(side=tk.LEFT, padx=(8, 6))
        self.shutdown_unit_menu = self._option_menu(
            self.shutdown_countdown_row, self.shutdown_unit_var, ("Minutos", "Horas"), width=8,
        )
        self.shutdown_unit_menu.pack(side=tk.LEFT)
        tk.Label(self.shutdown_countdown_row, text="(una sola vez)", font=FONTS["tiny"],
                 fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(side=tk.LEFT, padx=(6, 0))

        self.shutdown_warn_row = tk.Frame(card.body, bg=COLORS["surface"])
        self.shutdown_warn_row.pack(fill=tk.X, pady=(SPACING["sm"], 0))
        tk.Label(self.shutdown_warn_row, text="Avisar", font=FONTS["small"],
                 fg=COLORS["text_secondary"], bg=COLORS["surface"]).pack(side=tk.LEFT)
        self.shutdown_warn_spinner = self._spinbox(self.shutdown_warn_row, self.shutdown_warn_var, 0, 30, width=3)
        self.shutdown_warn_spinner.pack(side=tk.LEFT, padx=(8, 6))
        tk.Label(self.shutdown_warn_row, text="min antes (0 = sin aviso)", font=FONTS["tiny"],
                 fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(side=tk.LEFT)

        actions = tk.Frame(card.body, bg=COLORS["surface"])
        actions.pack(fill=tk.X, pady=(SPACING["md"], 0))
        self.shutdown_now_btn = make_button(
            actions, "Apagar ahora (60 s)", self._on_shutdown_now_click, kind="ghost", pad=(10, 5),
        )
        self.shutdown_now_btn.pack(side=tk.LEFT)
        self.shutdown_postpone_btn = make_button(
            actions, f"Posponer {DEFAULT_POSTPONE_MINUTES} min", self._on_shutdown_postpone_click,
            kind="ghost", pad=(10, 5),
        )
        self.shutdown_postpone_btn.pack(side=tk.LEFT, padx=(6, 0))

        cancel_row = tk.Frame(card.body, bg=COLORS["surface"])
        cancel_row.pack(fill=tk.X, pady=(SPACING["sm"], 0))
        self.shutdown_cancel_btn = make_button(
            cancel_row, "Cancelar apagado", self._on_shutdown_cancel_click, kind="danger", pad=(10, 5),
        )
        self.shutdown_cancel_btn.pack(side=tk.RIGHT)

        self.shutdown_mode_var.trace_add("write", self._on_shutdown_changed)
        self.shutdown_hour_var.trace_add("write", self._on_shutdown_changed)
        self.shutdown_minute_var.trace_add("write", self._on_shutdown_changed)
        self.shutdown_minutes_var.trace_add("write", self._on_shutdown_changed)
        self.shutdown_warn_var.trace_add("write", self._on_shutdown_changed)
        self.shutdown_unit_var.trace_add("write", self._on_shutdown_unit_change)

    def _build_startup(self, parent):
        card = Card(parent)
        card.pack(fill=tk.X, pady=(0, SPACING["md"]))
        self._toggle_row(card.body, "Iniciar con Windows", self.auto_start_var,
                         self._on_autostart_toggle_click)
        self._toggle_row(card.body, "Iniciar minimizado", self.start_minimized_var,
                         self._on_start_minimized_toggle_click, top_pad=SPACING["sm"])
        tk.Label(card.body, text="Minimizado: la ventana no se abre hasta clic en el icono.",
                 font=FONTS["tiny"], fg=COLORS["text_muted"], bg=COLORS["surface"],
                 wraplength=280, justify="left").pack(anchor="w", pady=(SPACING["sm"], 0))

    def _build_footer(self, parent):
        footer = tk.Frame(parent, bg=COLORS["bg_dark"])
        footer.pack(fill=tk.X, pady=(SPACING["xs"], 0))
        make_button(footer, "Exportar CSV", self._on_export_click, kind="ghost").pack(side=tk.LEFT)
        tk.Label(footer, text="Doble clic en el tray para abrir/cerrar", font=FONTS["tiny"],
                 fg=COLORS["text_muted"], bg=COLORS["bg_dark"]).pack(side=tk.RIGHT)

    # ─── Helpers de widgets ──────────────────────────────────────────────

    def _spinbox(self, parent, var, lo, hi, width=3):
        return tk.Spinbox(
            parent, from_=lo, to=hi, width=width, font=FONTS["body"],
            bg=COLORS["surface_3"], fg=COLORS["text_primary"],
            buttonbackground=COLORS["surface_3"], relief="flat",
            highlightthickness=0, textvariable=var, justify="center",
            insertbackground=COLORS["text_primary"],
        )

    def _option_menu(self, parent, var, options, width=8):
        menu = tk.OptionMenu(parent, var, *options)
        menu.configure(
            font=FONTS["small"], bg=COLORS["surface_3"], fg=COLORS["text_primary"],
            activebackground=COLORS["accent"], activeforeground=COLORS["on_accent"],
            relief="flat", highlightthickness=0, width=width, anchor="w",
            padx=6,
        )
        menu["menu"].configure(bg=COLORS["surface_2"], fg=COLORS["text_primary"],
                               activebackground=COLORS["accent"], activeforeground=COLORS["on_accent"])
        return menu

    def _toggle_row(self, parent, title, var, command, right_factory=None, top_pad=0):
        row = tk.Frame(parent, bg=COLORS["surface"])
        row.pack(fill=tk.X, pady=(top_pad, 0))
        tk.Label(row, text=title, font=FONTS["card_title"], fg=COLORS["text_primary"],
                 bg=COLORS["surface"]).pack(side=tk.LEFT)
        right = tk.Frame(row, bg=COLORS["surface"])
        right.pack(side=tk.RIGHT)
        switch = ToggleSwitch(right, var, command=command)
        switch.pack(side=tk.RIGHT)
        if right_factory is not None:
            right_factory(right).pack(side=tk.RIGHT, padx=(0, 12))
        return row

    def _make_game_dot(self, parent):
        self.game_status_dot = tk.Label(parent, text="●", font=FONTS["body"],
                                        fg=COLORS["text_muted"], bg=COLORS["surface"])
        return self.game_status_dot

    # ─── Actualización ───────────────────────────────────────────────────

    def _reference_seconds(self) -> int:
        if self.settings.get("screen_lock_enabled", False):
            return max(1, int(self.settings.get("screen_lock_minutes", 240))) * 60
        return max(1, self.settings.get("daily_goal_hours", 8)) * 3600

    @staticmethod
    def _format_duration(seconds: int) -> str:
        minutes = seconds // 60
        if minutes >= 60 and minutes % 60 == 0:
            return f"{minutes // 60}h"
        return f"{minutes}m"

    def _start_update_loop(self):
        try:
            self._update_display()
        except Exception:
            pass
        if self.root:
            self._update_job = self.root.after(1000, self._start_update_loop)

    def _update_display(self):
        try:
            elapsed_str = self.logger.get_elapsed_short()
            self.time_var.set(elapsed_str)

            if self.notifier.is_paused:
                self.status_var.set("Pausado")
                self.status_pill.configure(fg=COLORS["text_warning"])
            else:
                self.status_var.set("Activo")
                self.status_pill.configure(fg=COLORS["accent_green_light"])

            stats = self.logger.get_today_stats()
            self.today_total_var.set(self.logger.format_seconds(stats["total_seconds"]))
            self.sessions_var.set(str(stats["sessions_count"]))
            self.session_var.set(self.logger.format_seconds(stats["current_session_seconds"]))

            self._draw_progress(stats["current_session_seconds"])
            self._draw_goal(stats["total_seconds"])
            self._draw_week_chart()
        except Exception:
            pass

    def _draw_progress(self, current_seconds: int):
        ref_seconds = self._reference_seconds()
        progress = min(current_seconds / ref_seconds, 1.0)
        color = self._progress_color(progress)
        formatted = self.logger.format_seconds(current_seconds)
        label = self._format_duration(ref_seconds)
        self.ring.set(progress, color, main=self.logger.get_elapsed_short(), sub="Sesión actual")
        self.progress_bar.set(progress, color, text=f"{int(progress * 100)}%  ·  {formatted} / {label}")

    @staticmethod
    def _progress_color(progress: float) -> str:
        if progress < 0.5:
            return COLORS["progress_fill"]
        if progress < 0.8:
            return COLORS["progress_warning"]
        return COLORS["progress_danger"]

    def _draw_goal(self, total_seconds: int):
        goal_hours = self._daily_goal_hours
        goal_seconds = max(1, goal_hours) * 3600
        progress = min(total_seconds / goal_seconds, 1.0)
        color = self._progress_color(progress)
        self.goal_bar.set(progress, color, text=f"{int(progress * 100)}%  ·  meta {goal_hours}h")
        self.daily_goal_var.set(f"{total_seconds // 3600}h {(total_seconds % 3600) // 60}m / {goal_hours}h")

    def _draw_week_chart(self):
        try:
            self.week_chart.render(self.logger.get_week_stats())
        except Exception:
            pass

    def set_daily_goal(self, hours: int):
        self._daily_goal_hours = hours

    # ─── Scroll ──────────────────────────────────────────────────────────

    def _on_mousewheel(self, event):
        self._scroll_by(event.delta)

    def _on_touchpad_scroll(self, event):
        _dx, dy = unpack_touchpad_delta(event.delta)
        self._scroll_by(dy)

    def _scroll_by(self, delta: int):
        if not delta:
            return
        self._wheel_delta += (delta / 120.0) * SCROLL_PIXELS_PER_NOTCH
        if abs(self._wheel_delta) < SCROLL_MIN_STEP:
            return
        pixels = int(self._wheel_delta)
        if pixels == 0:
            pixels = SCROLL_MIN_STEP if self._wheel_delta > 0 else -SCROLL_MIN_STEP
        self._wheel_delta -= pixels
        self._canvas.yview_scroll(-pixels, "units")

    def _on_content_configure(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._canvas.after_idle(self._update_scroll_state)

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)
        self._canvas.after_idle(self._update_scroll_state)

    def _update_scroll_state(self):
        """Muestra la barra solo si el contenido no cabe (p. ej. ventana chica)."""
        if not self.root or not self._canvas.winfo_exists():
            return
        self._canvas.update_idletasks()
        bbox = self._canvas.bbox("all")
        content_h = (bbox[3] - bbox[1]) if bbox else 0
        needed = content_h > self._canvas.winfo_height() + 2
        mapped = bool(self._scrollbar.winfo_ismapped())
        if needed and not mapped:
            self._scrollbar.pack(side="right", fill="y")
            self._canvas.configure(yscrollcommand=self._scrollbar.set)
        elif not needed and mapped:
            self._scrollbar.pack_forget()
            self._canvas.configure(yscrollcommand="")
            self._canvas.yview_moveto(0)

    # ─── Acciones (handlers puente) ──────────────────────────────────────

    def _on_pomodoro_start_click(self):
        if self._on_pomodoro_start:
            self._on_pomodoro_start()

    def _on_pomodoro_stop_click(self):
        if self._on_pomodoro_stop:
            self._on_pomodoro_stop()

    def _on_pomodoro_skip_click(self):
        if self._on_pomodoro_skip:
            self._on_pomodoro_skip()

    def _on_export_click(self):
        if self._on_export_csv:
            self._on_export_csv()

    def _on_daily_goal_toggle_click(self, *_args):
        if self._on_daily_goal_toggle:
            self._on_daily_goal_toggle(self.daily_goal_enabled.get())

    def _on_goal_hours_change(self, *_args):
        try:
            val = max(1, min(16, int(self.daily_goal_hours_var.get())))
            self._daily_goal_hours = val
            if self._on_daily_goal_change:
                self._on_daily_goal_change(val)
        except (ValueError, tk.TclError):
            pass

    def _on_pomodoro_toggle_click(self, *_args):
        if self._on_pomodoro_toggle:
            self._on_pomodoro_toggle(self.pomodoro_enabled.get())

    def _on_game_mode_toggle_click(self, *_args):
        if self._on_game_mode_toggle:
            self._on_game_mode_toggle(self.game_mode_enabled.get())

    def _on_screen_lock_toggle_click(self, *_args):
        if self._on_screen_lock_toggle:
            self._on_screen_lock_toggle(self.screen_lock_enabled.get())

    def _on_lock_change(self, *_args):
        if self._suppress_callbacks:
            return
        try:
            val = max(1, int(self.lock_val_var.get()))
        except (ValueError, tk.TclError):
            return
        minutes = val if self.lock_unit_var.get() == "Minutos" else val * 60
        if self._on_screen_lock_change:
            self._on_screen_lock_change(minutes)

    def _on_lock_unit_change(self, *_args):
        if self.lock_unit_var.get() == "Minutos":
            self.lock_val_spinner.config(from_=1, to=720)
        else:
            self.lock_val_spinner.config(from_=1, to=12)
        self._on_lock_change()

    # ─── Apagado automático ──────────────────────────────────────────────

    def _on_shutdown_toggle_click(self, *_args):
        self._update_shutdown_widgets()
        self._cancel_shutdown_emit()
        self._emit_shutdown_change()

    def _on_shutdown_changed(self, *_args):
        if self._suppress_callbacks:
            return
        self._update_shutdown_widgets()
        if not self.root:
            self._emit_shutdown_change()
            return
        self._cancel_shutdown_emit()
        self._shutdown_emit_job = self.root.after(600, self._emit_shutdown_change)

    def _on_shutdown_unit_change(self, *_args):
        if self.shutdown_unit_var.get() == "Horas":
            self.shutdown_minutes_spinner.config(from_=1, to=12)
        else:
            self.shutdown_minutes_spinner.config(from_=1, to=720)
        self._on_shutdown_changed()

    def _cancel_shutdown_emit(self):
        if self._shutdown_emit_job and self.root:
            try:
                self.root.after_cancel(self._shutdown_emit_job)
            except (ValueError, tk.TclError):
                pass
        self._shutdown_emit_job = None

    def _emit_shutdown_change(self):
        self._shutdown_emit_job = None
        if self._on_shutdown_change:
            self._on_shutdown_change(self._collect_shutdown_config())

    def _collect_shutdown_config(self) -> dict:
        def _int(var, default, low, high):
            try:
                return max(low, min(high, int(var.get())))
            except (ValueError, tk.TclError):
                return default

        hour = _int(self.shutdown_hour_var, 23, 0, 23)
        minute = _int(self.shutdown_minute_var, 0, 0, 59)
        if self.shutdown_unit_var.get() == "Horas":
            minutes = _int(self.shutdown_minutes_var, 1, 1, 12) * 60
        else:
            minutes = _int(self.shutdown_minutes_var, 60, 1, 720)
        return {
            "enabled": bool(self.shutdown_enabled.get()),
            "mode": SHUTDOWN_MODE_KEYS.get(self.shutdown_mode_var.get(), "hora"),
            "time": f"{hour:02d}:{minute:02d}",
            "minutes": minutes,
            "warn_minutes": _int(self.shutdown_warn_var, 5, 0, 30),
        }

    def _update_shutdown_widgets(self):
        if not hasattr(self, "shutdown_mode_menu"):
            return
        enabled = bool(self.shutdown_enabled.get())
        is_countdown = SHUTDOWN_MODE_KEYS.get(self.shutdown_mode_var.get(), "hora") == "temporizador"
        self.shutdown_mode_menu.configure(state="normal" if enabled else "disabled")
        self.shutdown_warn_spinner.configure(state="normal" if enabled else "disabled")
        self.shutdown_postpone_btn.configure(state="normal" if enabled else "disabled")
        self.shutdown_hour_spinner.configure(state="normal" if enabled and not is_countdown else "disabled")
        self.shutdown_minute_spinner.configure(state="normal" if enabled and not is_countdown else "disabled")
        self.shutdown_minutes_spinner.configure(state="normal" if enabled and is_countdown else "disabled")
        self.shutdown_unit_menu.configure(state="normal" if enabled and is_countdown else "disabled")
        self.shutdown_time_row.pack_forget()
        self.shutdown_countdown_row.pack_forget()
        if is_countdown:
            self.shutdown_countdown_row.pack(fill=tk.X, pady=(SPACING["sm"], 0), before=self.shutdown_warn_row)
        else:
            self.shutdown_time_row.pack(fill=tk.X, pady=(SPACING["sm"], 0), before=self.shutdown_warn_row)

    def _on_shutdown_now_click(self):
        if self._on_shutdown_now:
            self._on_shutdown_now()

    def _on_shutdown_postpone_click(self):
        if self._on_shutdown_postpone:
            self._on_shutdown_postpone()

    def _on_shutdown_cancel_click(self):
        if self._on_shutdown_cancel:
            self._on_shutdown_cancel()

    def _on_autostart_toggle_click(self, *_args):
        if self._on_autostart_toggle:
            self._on_autostart_toggle(self.auto_start_var.get())

    def _on_start_minimized_toggle_click(self, *_args):
        if self._on_start_minimized_toggle:
            self._on_start_minimized_toggle(self.start_minimized_var.get())

    # ─── Setters usados por la app ───────────────────────────────────────

    def set_shutdown_status(self, text: str):
        self.shutdown_status_var.set(text)

    def set_shutdown_enabled(self, enabled: bool):
        self.shutdown_enabled.set(bool(enabled))
        self._update_shutdown_widgets()

    def set_autostart(self, enabled: bool):
        self.auto_start_var.set(bool(enabled))

    def set_start_minimized(self, enabled: bool):
        self.start_minimized_var.set(bool(enabled))

    def set_toggles_from_settings(self, settings: dict):
        self._suppress_callbacks = True
        try:
            self.daily_goal_enabled.set(settings.get("daily_goal_enabled", False))
            self.pomodoro_enabled.set(settings.get("pomodoro_enabled", False))
            self.game_mode_enabled.set(settings.get("game_mode_enabled", False))
            self.screen_lock_enabled.set(settings.get("screen_lock_enabled", False))
            self.daily_goal_hours_var.set(str(settings.get("daily_goal_hours", 8)))
            lock_minutes = int(settings.get("screen_lock_minutes", 240))
            if lock_minutes % 60 == 0:
                self.lock_unit_var.set("Horas")
                self.lock_val_var.set(str(lock_minutes // 60))
            else:
                self.lock_unit_var.set("Minutos")
                self.lock_val_var.set(str(lock_minutes))
            self.shutdown_enabled.set(settings.get("shutdown_enabled", False))
            self.shutdown_mode_var.set(SHUTDOWN_MODE_LABELS.get(settings.get("shutdown_mode", "hora"), "Hora fija"))
            hour, _, minute = str(settings.get("shutdown_time", "23:00")).partition(":")
            self.shutdown_hour_var.set(hour or "23")
            self.shutdown_minute_var.set(minute or "00")
            mins = int(settings.get("shutdown_minutes", 60))
            if mins % 60 == 0:
                self.shutdown_unit_var.set("Horas")
                self.shutdown_minutes_var.set(str(mins // 60))
            else:
                self.shutdown_unit_var.set("Minutos")
                self.shutdown_minutes_var.set(str(mins))
            self.shutdown_warn_var.set(str(settings.get("shutdown_warn_minutes", 5)))
            self.auto_start_var.set(settings.get("auto_start", False))
            self.start_minimized_var.set(settings.get("start_minimized", True))
        finally:
            self._suppress_callbacks = False
        self._update_shutdown_widgets()

    def set_interval_from_settings(self, interval_seconds: int, overlay_seconds: int = 8):
        if interval_seconds % 3600 == 0 and interval_seconds >= 3600:
            self.interval_unit_var.set("Horas")
            self.interval_val_var.set(str(interval_seconds // 3600))
        elif interval_seconds % 60 == 0 and interval_seconds >= 60:
            self.interval_unit_var.set("Minutos")
            self.interval_val_var.set(str(interval_seconds // 60))
        else:
            self.interval_unit_var.set("Segundos")
            self.interval_val_var.set(str(interval_seconds))
        self._on_unit_change_inline()
        self.overlay_var.set(str(overlay_seconds))

    def _on_unit_change_inline(self, *_args):
        unit = self.interval_unit_var.get()
        if unit == "Segundos":
            self.interval_spinner.config(from_=1, to=59)
        elif unit == "Minutos":
            self.interval_spinner.config(from_=1, to=120)
        elif unit == "Horas":
            self.interval_spinner.config(from_=1, to=12)

    def _on_apply_interval(self):
        try:
            val = int(self.interval_val_var.get())
            if val < 1:
                return
            unit = self.interval_unit_var.get()
            seconds = val if unit == "Segundos" else val * 60 if unit == "Minutos" else val * 3600
            if self._on_interval_change:
                self._on_interval_change(seconds)
            try:
                overlay_val = max(2, min(30, int(self.overlay_var.get())))
            except (ValueError, tk.TclError):
                overlay_val = 8
            if self._on_overlay_change:
                self._on_overlay_change(overlay_val)
        except (ValueError, tk.TclError):
            pass

    # ─── Ventana: mostrar/cerrar ─────────────────────────────────────────

    def show(self):
        if self.root:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self._visible = True

    def hide(self):
        if self.root:
            self.root.withdraw()
            self._visible = False

    def _center_window(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"+{x}+{y}")

    def get_geometry(self) -> str:
        if self.root:
            return self.root.geometry()
        return ""

    def _on_close(self):
        self.hide()

    def destroy(self):
        self._cancel_shutdown_emit()
        if self._update_job and self.root:
            self.root.after_cancel(self._update_job)
        if self.root:
            self.root.destroy()
            self.root = None
        self._visible = False

    @property
    def is_visible(self) -> bool:
        return self._visible
