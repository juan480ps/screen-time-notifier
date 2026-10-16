"""Interfaz gráfica principal de la aplicación."""

import tkinter as tk
from typing import Optional

from screentime.config import ICON_PATH, get_app_name, get_app_version
from screentime.shutdown import DEFAULT_POSTPONE_MINUTES
from screentime.theme import (
    COLORS,
    SCROLL_MIN_STEP,
    SCROLL_PIXELS_PER_NOTCH,
    SHUTDOWN_MODE_KEYS,
    SHUTDOWN_MODE_LABELS,
    unpack_touchpad_delta,
)


class MainGUI:
    """Ventana principal de la aplicación con diseño gaming."""

    def __init__(self, logger, notifier, settings: dict = None):
        self.logger = logger
        self.notifier = notifier
        self.settings = settings or {}
        self.root: Optional[tk.Tk] = None
        self._update_job = None
        self._visible = False
        self.time_var = None
        self.status_var = None
        self.today_total_var = None
        self.sessions_var = None
        self.session_var = None
        self.interval_val_var = None
        self.interval_unit_var = None
        self._on_interval_change = None
        self._on_overlay_change = None
        self.pomodoro_state_var = None
        self.pomodoro_timer_var = None
        self.daily_goal_var = None
        self.game_mode_var = None
        self.screen_lock_var = None
        self._on_pomodoro_start = None
        self._on_pomodoro_stop = None
        self._on_pomodoro_skip = None
        self._on_export_csv = None
        self._on_daily_goal_toggle = None
        self._on_pomodoro_toggle = None
        self._on_game_mode_toggle = None
        self._on_screen_lock_toggle = None
        self._on_screen_lock_hours_change = None
        self._on_daily_goal_change = None
        self._on_shutdown_change = None
        self._on_shutdown_now = None
        self._on_shutdown_postpone = None
        self._on_shutdown_cancel = None
        self._on_autostart_toggle = None
        self._on_start_minimized_toggle = None
        self._suppress_callbacks = False
        self._shutdown_emit_job = None
        self._wheel_delta = 0.0

    def create_window(self, start_minimized: bool = False) -> tk.Tk:
        if self.root is not None:
            self.root.deiconify()
            self.root.lift()
            self._visible = True
            return self.root

        self.root = tk.Tk()
        if start_minimized:
            # Se oculta antes de dibujar nada para que no aparezca la ventana
            self.root.withdraw()

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
        self.daily_goal_var = tk.StringVar(value="0%")
        self.game_mode_var = tk.StringVar(value="Desactivado")
        self.screen_lock_var = tk.StringVar(value="Desactivado")
        self.daily_goal_enabled = tk.BooleanVar(value=False)
        self.pomodoro_enabled = tk.BooleanVar(value=False)
        self.game_mode_enabled = tk.BooleanVar(value=False)
        self.screen_lock_enabled = tk.BooleanVar(value=False)
        self.daily_goal_hours_var = tk.StringVar(value="8")
        self.shutdown_enabled = tk.BooleanVar(value=False)
        self.auto_start_var = tk.BooleanVar(value=False)
        self.start_minimized_var = tk.BooleanVar(value=True)
        self.shutdown_mode_var = tk.StringVar(value="Hora fija")
        self.shutdown_hour_var = tk.StringVar(value="23")
        self.shutdown_minute_var = tk.StringVar(value="00")
        self.shutdown_minutes_var = tk.StringVar(value="60")
        self.shutdown_warn_var = tk.StringVar(value="5")
        self.shutdown_status_var = tk.StringVar(value="Desactivado")
        self.root.title(f"{get_app_name()} v{get_app_version()}")
        self.root.minsize(400, 500)
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
            self.root.geometry("480x820")
            # Una ventana oculta reporta tamaño 1x1, así que no se puede centrar
            if not start_minimized:
                self._center_window()

        self._build_ui()
        self._start_update_loop()
        self._visible = not start_minimized

        return self.root

    def _build_ui(self):
        """Construye toda la interfaz de usuario con scroll."""
        self._canvas = tk.Canvas(
            self.root, bg=COLORS["bg_dark"], highlightthickness=0, yscrollincrement=1,
        )
        self._scrollbar = tk.Scrollbar(self.root, orient="vertical", command=self._canvas.yview)
        self._scroll_frame = tk.Frame(self._canvas, bg=COLORS["bg_dark"])

        self._scroll_frame.bind("<Configure>", lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas_window = self._canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._canvas.pack(side="left", fill="both", expand=True)
        self._scrollbar.pack(side="right", fill="y")

        def _on_canvas_configure(event):
            self._canvas.itemconfig(self._canvas_window, width=event.width)

        self._canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event):
            # Rueda de ratón clásica (múltiplos de 120).
            self._scroll_by(event.delta)

        def _on_touchpad_scroll(event):
            # Tk 9.0 entrega el gesto de dos dedos como <TouchpadScroll>
            # (no como <MouseWheel>): se extrae el desplazamiento vertical.
            _dx, dy = unpack_touchpad_delta(event.delta)
            self._scroll_by(dy)

        self._canvas.bind_all("<MouseWheel>", _on_mousewheel)
        try:
            self._canvas.bind_all("<TouchpadScroll>", _on_touchpad_scroll)
        except tk.TclError:
            # Tk < 9.0 no conoce <TouchpadScroll>; en esas versiones el scroll
            # de trackpad llega como <MouseWheel> con deltas pequeños, que ya
            # cubre el acumulador de _on_mousewheel.
            pass

        content = self._scroll_frame

        # ─── Header ──────────────────────────────────────────────────────
        header = tk.Frame(content, bg=COLORS["bg_dark"], height=60)
        header.pack(fill=tk.X, padx=0, pady=(10, 0))
        header.pack_propagate(False)

        tk.Label(
            header, text="SCREEN TIME",
            font=("Segoe UI", 18, "bold"),
            fg=COLORS["accent_neon"], bg=COLORS["bg_dark"],
        ).pack(pady=(5, 0))

        tk.Label(
            header, text="Monitor de tiempo en pantalla",
            font=("Segoe UI", 9),
            fg=COLORS["text_secondary"], bg=COLORS["bg_dark"],
        ).pack()

        # ─── Timer principal ─────────────────────────────────────────────
        timer_frame = tk.Frame(
            content, bg=COLORS["bg_panel"],
            highlightbackground=COLORS["border"], highlightthickness=1,
        )
        timer_frame.pack(fill=tk.X, padx=20, pady=(15, 10))

        tk.Label(
            timer_frame, text="TIEMPO DE SESIÓN",
            font=("Segoe UI", 9, "bold"),
            fg=COLORS["text_secondary"], bg=COLORS["bg_panel"],
        ).pack(pady=(12, 0))

        self.timer_label = tk.Label(
            timer_frame, textvariable=self.time_var,
            font=("Consolas", 40, "bold"),
            fg=COLORS["accent_neon"], bg=COLORS["bg_panel"],
        )
        self.timer_label.pack(pady=(5, 5))

        self.status_label = tk.Label(
            timer_frame, textvariable=self.status_var,
            font=("Segoe UI", 9),
            fg=COLORS["accent_green_light"], bg=COLORS["bg_panel"],
        )
        self.status_label.pack(pady=(0, 12))

        # ─── Barra de progreso ───────────────────────────────────────────
        progress_frame = tk.Frame(content, bg=COLORS["bg_dark"])
        progress_frame.pack(fill=tk.X, padx=20, pady=(5, 5))

        tk.Label(
            progress_frame, text="PROGRESO DE SESIÓN",
            font=("Segoe UI", 8, "bold"),
            fg=COLORS["text_secondary"], bg=COLORS["bg_dark"], anchor="w",
        ).pack(fill=tk.X)

        self.progress_canvas = tk.Canvas(
            progress_frame, height=20,
            bg=COLORS["progress_bg"], highlightthickness=0,
        )
        self.progress_canvas.pack(fill=tk.X, pady=(4, 0))

        # ─── Estadísticas del día ────────────────────────────────────────
        stats_frame = tk.Frame(
            content, bg=COLORS["bg_panel"],
            highlightbackground=COLORS["border"], highlightthickness=1,
        )
        stats_frame.pack(fill=tk.X, padx=20, pady=(10, 10))

        tk.Label(
            stats_frame, text="ESTADÍSTICAS DE HOY",
            font=("Segoe UI", 9, "bold"),
            fg=COLORS["text_secondary"], bg=COLORS["bg_panel"],
        ).pack(pady=(10, 8))

        grid = tk.Frame(stats_frame, bg=COLORS["bg_panel"])
        grid.pack(fill=tk.X, padx=15, pady=(0, 12))

        col1 = tk.Frame(grid, bg=COLORS["bg_card"], padx=10, pady=8)
        col1.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(0, 4))
        tk.Label(
            col1, text="Total hoy", font=("Segoe UI", 8),
            fg=COLORS["text_secondary"], bg=COLORS["bg_card"],
        ).pack()
        tk.Label(
            col1, textvariable=self.today_total_var, font=("Segoe UI", 14, "bold"),
            fg=COLORS["accent_neon"], bg=COLORS["bg_card"],
        ).pack()

        col2 = tk.Frame(grid, bg=COLORS["bg_card"], padx=10, pady=8)
        col2.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=2)
        tk.Label(
            col2, text="Sesiones", font=("Segoe UI", 8),
            fg=COLORS["text_secondary"], bg=COLORS["bg_card"],
        ).pack()
        tk.Label(
            col2, textvariable=self.sessions_var, font=("Segoe UI", 14, "bold"),
            fg=COLORS["accent_green_light"], bg=COLORS["bg_card"],
        ).pack()

        col3 = tk.Frame(grid, bg=COLORS["bg_card"], padx=10, pady=8)
        col3.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(4, 0))
        tk.Label(
            col3, text="Actual", font=("Segoe UI", 8),
            fg=COLORS["text_secondary"], bg=COLORS["bg_card"],
        ).pack()
        tk.Label(
            col3, textvariable=self.session_var, font=("Segoe UI", 14, "bold"),
            fg=COLORS["accent_green"], bg=COLORS["bg_card"],
        ).pack()

        # ─── Configurar intervalo ────────────────────────────────────────
        interval_frame = tk.Frame(
            content, bg=COLORS["bg_panel"],
            highlightbackground=COLORS["border"], highlightthickness=1,
        )
        interval_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        tk.Label(
            interval_frame, text="CONFIGURAR INTERVALO",
            font=("Segoe UI", 9, "bold"),
            fg=COLORS["text_secondary"], bg=COLORS["bg_panel"],
        ).pack(pady=(10, 6))

        interval_input = tk.Frame(interval_frame, bg=COLORS["bg_panel"])
        interval_input.pack(pady=(0, 10))

        self.interval_spinner = tk.Spinbox(
            interval_input, from_=1, to=120, increment=1, width=5,
            font=("Segoe UI", 12),
            bg=COLORS["bg_card"], fg=COLORS["accent_neon"],
            buttonbackground=COLORS["accent_green"],
            highlightthickness=0, textvariable=self.interval_val_var,
        )
        self.interval_spinner.pack(side=tk.LEFT, padx=(0, 8))

        self.interval_unit_menu = tk.OptionMenu(
            interval_input, self.interval_unit_var,
            "Segundos", "Minutos", "Horas",
        )
        self.interval_unit_menu.configure(
            font=("Segoe UI", 9),
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            activebackground=COLORS["accent_green"], activeforeground="white",
            highlightthickness=0, width=8,
        )
        self.interval_unit_menu["menu"].configure(
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            activebackground=COLORS["accent_green"],
        )
        self.interval_unit_menu.pack(side=tk.LEFT)

        self.interval_apply_btn = tk.Button(
            interval_input, text="Aplicar",
            font=("Segoe UI", 9, "bold"),
            bg=COLORS["accent_green"], fg="white",
            padx=12, command=self._on_apply_interval,
        )
        self.interval_apply_btn.pack(side=tk.LEFT, padx=(10, 0))

        self.interval_unit_var.trace_add("write", self._on_unit_change_inline)

        overlay_row = tk.Frame(interval_frame, bg=COLORS["bg_panel"])
        overlay_row.pack(fill=tk.X, padx=15, pady=(0, 10))

        tk.Label(
            overlay_row, text="Popup visible:",
            font=("Segoe UI", 9),
            fg=COLORS["text_secondary"], bg=COLORS["bg_panel"],
        ).pack(side=tk.LEFT)

        self.overlay_spinner = tk.Spinbox(
            overlay_row, from_=2, to=30, increment=1, width=3,
            font=("Segoe UI", 11),
            bg=COLORS["bg_card"], fg=COLORS["accent_neon"],
            buttonbackground=COLORS["accent_green"],
            highlightthickness=0, textvariable=self.overlay_var,
        )
        self.overlay_spinner.pack(side=tk.LEFT, padx=(5, 5))

        tk.Label(
            overlay_row, text="seg",
            font=("Segoe UI", 9),
            fg=COLORS["text_secondary"], bg=COLORS["bg_panel"],
        ).pack(side=tk.LEFT)

        # ─── Barra de progreso semanal ───────────────────────────────────
        week_frame = tk.Frame(
            content, bg=COLORS["bg_panel"],
            highlightbackground=COLORS["border"], highlightthickness=1,
        )
        week_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        tk.Label(
            week_frame, text="ACTIVIDAD SEMANAL",
            font=("Segoe UI", 8, "bold"),
            fg=COLORS["text_secondary"], bg=COLORS["bg_panel"],
        ).pack(pady=(8, 4))

        self.week_canvas = tk.Canvas(
            week_frame, height=50,
            bg=COLORS["bg_panel"], highlightthickness=0,
        )
        self.week_canvas.pack(fill=tk.X, padx=10, pady=(0, 8))

        # ─── FEATURES OPCIONALES ────────────────────────────────────────
        features_frame = tk.Frame(content, bg=COLORS["bg_dark"])
        features_frame.pack(fill=tk.X, padx=20, pady=(0, 5))

        tk.Label(
            features_frame, text="FEATURES OPCIONALES",
            font=("Segoe UI", 9, "bold"), fg=COLORS["accent_neon"], bg=COLORS["bg_dark"],
        ).pack(pady=(0, 6))

        # ── Meta Diaria ──────────────────────────────────────────────────
        goal_frame = tk.Frame(
            features_frame, bg=COLORS["bg_panel"],
            highlightbackground=COLORS["border"], highlightthickness=1,
        )
        goal_frame.pack(fill=tk.X, pady=(0, 6))

        goal_header = tk.Frame(goal_frame, bg=COLORS["bg_panel"])
        goal_header.pack(fill=tk.X, padx=10, pady=(8, 4))

        tk.Checkbutton(
            goal_header, text="Meta diaria", variable=self.daily_goal_enabled,
            font=("Segoe UI", 9, "bold"), fg=COLORS["text_primary"], bg=COLORS["bg_panel"],
            selectcolor=COLORS["bg_card"], activebackground=COLORS["bg_panel"],
            command=self._on_daily_goal_toggle_click,
        ).pack(side=tk.LEFT)

        goal_hours_row = tk.Frame(goal_frame, bg=COLORS["bg_panel"])
        goal_hours_row.pack(fill=tk.X, padx=10, pady=(0, 4))

        self.goal_hours_spinner = tk.Spinbox(
            goal_hours_row, from_=1, to=16, width=3,
            font=("Segoe UI", 10), bg=COLORS["bg_card"], fg=COLORS["accent_neon"],
            buttonbackground=COLORS["accent_green"], highlightthickness=0,
            textvariable=self.daily_goal_hours_var,
        )
        self.goal_hours_spinner.pack(side=tk.LEFT, padx=(0, 4))

        tk.Label(goal_hours_row, text="horas máximo al día", font=("Segoe UI", 8),
                 fg=COLORS["text_secondary"], bg=COLORS["bg_panel"]).pack(side=tk.LEFT)

        self.daily_goal_hours_var.trace_add("write", self._on_goal_hours_change)

        self.goal_canvas = tk.Canvas(goal_frame, height=14, bg=COLORS["progress_bg"], highlightthickness=0)
        self.goal_canvas.pack(fill=tk.X, padx=10, pady=(0, 8))

        # ── Pomodoro ─────────────────────────────────────────────────────
        pomo_frame = tk.Frame(
            features_frame, bg=COLORS["bg_panel"],
            highlightbackground=COLORS["border"], highlightthickness=1,
        )
        pomo_frame.pack(fill=tk.X, pady=(0, 6))

        pomo_header = tk.Frame(pomo_frame, bg=COLORS["bg_panel"])
        pomo_header.pack(fill=tk.X, padx=10, pady=(8, 4))

        tk.Checkbutton(
            pomo_header, text="Modo Pomodoro", variable=self.pomodoro_enabled,
            font=("Segoe UI", 9, "bold"), fg=COLORS["text_primary"], bg=COLORS["bg_panel"],
            selectcolor=COLORS["bg_card"], activebackground=COLORS["bg_panel"],
            command=self._on_pomodoro_toggle_click,
        ).pack(side=tk.LEFT)

        pomo_body = tk.Frame(pomo_frame, bg=COLORS["bg_panel"])
        pomo_body.pack(fill=tk.X, padx=10, pady=(0, 2))

        self.pomo_state_label = tk.Label(
            pomo_body, textvariable=self.pomodoro_state_var,
            font=("Segoe UI", 9), fg=COLORS["accent_green_light"], bg=COLORS["bg_panel"],
        )
        self.pomo_state_label.pack(side=tk.LEFT)

        self.pomo_timer_label = tk.Label(
            pomo_body, textvariable=self.pomodoro_timer_var,
            font=("Consolas", 18, "bold"), fg=COLORS["accent_neon"], bg=COLORS["bg_panel"],
        )
        self.pomo_timer_label.pack(side=tk.RIGHT)

        pomo_footer = tk.Frame(pomo_frame, bg=COLORS["bg_panel"])
        pomo_footer.pack(fill=tk.X, padx=10, pady=(0, 8))

        self.pomo_cycle_label = tk.Label(
            pomo_footer, textvariable=self.pomodoro_cycle_var,
            font=("Segoe UI", 8), fg=COLORS["text_secondary"], bg=COLORS["bg_panel"],
        )
        self.pomo_cycle_label.pack(side=tk.LEFT)

        pomo_btns = tk.Frame(pomo_footer, bg=COLORS["bg_panel"])
        pomo_btns.pack(side=tk.RIGHT)

        self.pomo_start_btn = tk.Button(
            pomo_btns, text="▶ Iniciar", font=("Segoe UI", 8), bg=COLORS["accent_green"],
            fg="white", padx=6, command=self._on_pomodoro_start_click,
        )
        self.pomo_start_btn.pack(side=tk.LEFT, padx=2)

        self.pomo_skip_btn = tk.Button(
            pomo_btns, text="⏭ Saltar", font=("Segoe UI", 8), bg=COLORS["bg_card"],
            fg=COLORS["text_primary"], padx=6, command=self._on_pomodoro_skip_click,
        )
        self.pomo_skip_btn.pack(side=tk.LEFT, padx=2)

        self.pomo_stop_btn = tk.Button(
            pomo_btns, text="⏹ Parar", font=("Segoe UI", 8), bg=COLORS["text_danger"],
            fg="white", padx=6, command=self._on_pomodoro_stop_click,
        )
        self.pomo_stop_btn.pack(side=tk.LEFT, padx=2)

        # ── Modo Juego ──────────────────────────────────────────────────
        game_frame = tk.Frame(
            features_frame, bg=COLORS["bg_panel"],
            highlightbackground=COLORS["border"], highlightthickness=1,
        )
        game_frame.pack(fill=tk.X, pady=(0, 6))

        game_row = tk.Frame(game_frame, bg=COLORS["bg_panel"])
        game_row.pack(fill=tk.X, padx=10, pady=(8, 8))

        tk.Checkbutton(
            game_row, text="Modo juego (pausar en fullscreen)", variable=self.game_mode_enabled,
            font=("Segoe UI", 9, "bold"), fg=COLORS["text_primary"], bg=COLORS["bg_panel"],
            selectcolor=COLORS["bg_card"], activebackground=COLORS["bg_panel"],
            command=self._on_game_mode_toggle_click,
        ).pack(side=tk.LEFT)

        self.game_status_dot = tk.Label(
            game_row, text="●", font=("Segoe UI", 8), fg=COLORS["text_secondary"], bg=COLORS["bg_panel"],
        )
        self.game_status_dot.pack(side=tk.RIGHT)

        # ── Bloqueo de pantalla ─────────────────────────────────────────
        lock_frame = tk.Frame(
            features_frame, bg=COLORS["bg_panel"],
            highlightbackground=COLORS["border"], highlightthickness=1,
        )
        lock_frame.pack(fill=tk.X, pady=(0, 6))

        lock_row = tk.Frame(lock_frame, bg=COLORS["bg_panel"])
        lock_row.pack(fill=tk.X, padx=10, pady=(8, 4))

        tk.Checkbutton(
            lock_row, text="Bloqueo de pantalla", variable=self.screen_lock_enabled,
            font=("Segoe UI", 9, "bold"), fg=COLORS["text_primary"], bg=COLORS["bg_panel"],
            selectcolor=COLORS["bg_card"], activebackground=COLORS["bg_panel"],
            command=self._on_screen_lock_toggle_click,
        ).pack(side=tk.LEFT)

        self.lock_hours_var = tk.StringVar(value="4")
        lock_hours_row = tk.Frame(lock_frame, bg=COLORS["bg_panel"])
        lock_hours_row.pack(fill=tk.X, padx=10, pady=(0, 8))

        tk.Label(lock_hours_row, text="Bloquear después de", font=("Segoe UI", 8),
                 fg=COLORS["text_secondary"], bg=COLORS["bg_panel"]).pack(side=tk.LEFT)

        self.lock_hours_spinner = tk.Spinbox(
            lock_hours_row, from_=1, to=12, width=3,
            font=("Segoe UI", 10), bg=COLORS["bg_card"], fg=COLORS["accent_neon"],
            buttonbackground=COLORS["accent_green"], highlightthickness=0,
            textvariable=self.lock_hours_var,
        )
        self.lock_hours_spinner.pack(side=tk.LEFT, padx=(4, 4))

        tk.Label(lock_hours_row, text="horas", font=("Segoe UI", 8),
                 fg=COLORS["text_secondary"], bg=COLORS["bg_panel"]).pack(side=tk.LEFT)

        self.lock_hours_var.trace_add("write", self._on_lock_hours_change)

        # ── Apagado automático ─────────────────────────────────────
        shutdown_frame = tk.Frame(
            features_frame, bg=COLORS["bg_panel"],
            highlightbackground=COLORS["border"], highlightthickness=1,
        )
        shutdown_frame.pack(fill=tk.X, pady=(0, 6))

        shutdown_header = tk.Frame(shutdown_frame, bg=COLORS["bg_panel"])
        shutdown_header.pack(fill=tk.X, padx=10, pady=(8, 4))

        tk.Checkbutton(
            shutdown_header, text="Apagado automático", variable=self.shutdown_enabled,
            font=("Segoe UI", 9, "bold"), fg=COLORS["text_primary"], bg=COLORS["bg_panel"],
            selectcolor=COLORS["bg_card"], activebackground=COLORS["bg_panel"],
            command=self._on_shutdown_toggle_click,
        ).pack(side=tk.LEFT)

        self.shutdown_status_label = tk.Label(
            shutdown_header, textvariable=self.shutdown_status_var,
            font=("Segoe UI", 8), fg=COLORS["accent_green_light"], bg=COLORS["bg_panel"],
        )
        self.shutdown_status_label.pack(side=tk.RIGHT)

        self.shutdown_mode_row = tk.Frame(shutdown_frame, bg=COLORS["bg_panel"])
        self.shutdown_mode_row.pack(fill=tk.X, padx=10, pady=(0, 4))

        tk.Label(self.shutdown_mode_row, text="Modo:", font=("Segoe UI", 8),
                 fg=COLORS["text_secondary"], bg=COLORS["bg_panel"]).pack(side=tk.LEFT)

        self.shutdown_mode_menu = tk.OptionMenu(
            self.shutdown_mode_row, self.shutdown_mode_var, *SHUTDOWN_MODE_KEYS.keys(),
        )
        self.shutdown_mode_menu.configure(
            font=("Segoe UI", 8),
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            activebackground=COLORS["accent_green"], activeforeground="white",
            highlightthickness=0, width=12,
        )
        self.shutdown_mode_menu["menu"].configure(
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            activebackground=COLORS["accent_green"],
        )
        self.shutdown_mode_menu.pack(side=tk.LEFT, padx=(4, 0))

        self.shutdown_time_row = tk.Frame(shutdown_frame, bg=COLORS["bg_panel"])
        self.shutdown_time_row.pack(fill=tk.X, padx=10, pady=(0, 4))

        tk.Label(self.shutdown_time_row, text="Apagar a las", font=("Segoe UI", 8),
                 fg=COLORS["text_secondary"], bg=COLORS["bg_panel"]).pack(side=tk.LEFT)

        self.shutdown_hour_spinner = tk.Spinbox(
            self.shutdown_time_row, from_=0, to=23, width=3, format="%02.0f",
            font=("Segoe UI", 10), bg=COLORS["bg_card"], fg=COLORS["accent_neon"],
            buttonbackground=COLORS["accent_green"], highlightthickness=0,
            textvariable=self.shutdown_hour_var,
        )
        self.shutdown_hour_spinner.pack(side=tk.LEFT, padx=(4, 2))

        tk.Label(self.shutdown_time_row, text=":", font=("Segoe UI", 10, "bold"),
                 fg=COLORS["text_secondary"], bg=COLORS["bg_panel"]).pack(side=tk.LEFT)

        self.shutdown_minute_spinner = tk.Spinbox(
            self.shutdown_time_row, from_=0, to=59, width=3, format="%02.0f",
            font=("Segoe UI", 10), bg=COLORS["bg_card"], fg=COLORS["accent_neon"],
            buttonbackground=COLORS["accent_green"], highlightthickness=0,
            textvariable=self.shutdown_minute_var,
        )
        self.shutdown_minute_spinner.pack(side=tk.LEFT, padx=(2, 4))

        tk.Label(self.shutdown_time_row, text="(cada día)", font=("Segoe UI", 8),
                 fg=COLORS["text_secondary"], bg=COLORS["bg_panel"]).pack(side=tk.LEFT)

        self.shutdown_countdown_row = tk.Frame(shutdown_frame, bg=COLORS["bg_panel"])
        self.shutdown_countdown_row.pack(fill=tk.X, padx=10, pady=(0, 4))

        tk.Label(self.shutdown_countdown_row, text="Apagar en", font=("Segoe UI", 8),
                 fg=COLORS["text_secondary"], bg=COLORS["bg_panel"]).pack(side=tk.LEFT)

        self.shutdown_minutes_spinner = tk.Spinbox(
            self.shutdown_countdown_row, from_=1, to=720, width=4,
            font=("Segoe UI", 10), bg=COLORS["bg_card"], fg=COLORS["accent_neon"],
            buttonbackground=COLORS["accent_green"], highlightthickness=0,
            textvariable=self.shutdown_minutes_var,
        )
        self.shutdown_minutes_spinner.pack(side=tk.LEFT, padx=(4, 4))

        tk.Label(self.shutdown_countdown_row, text="minutos (una sola vez)", font=("Segoe UI", 8),
                 fg=COLORS["text_secondary"], bg=COLORS["bg_panel"]).pack(side=tk.LEFT)

        self.shutdown_warn_row = tk.Frame(shutdown_frame, bg=COLORS["bg_panel"])
        self.shutdown_warn_row.pack(fill=tk.X, padx=10, pady=(0, 6))

        tk.Label(self.shutdown_warn_row, text="Avisar", font=("Segoe UI", 8),
                 fg=COLORS["text_secondary"], bg=COLORS["bg_panel"]).pack(side=tk.LEFT)

        self.shutdown_warn_spinner = tk.Spinbox(
            self.shutdown_warn_row, from_=0, to=30, width=3,
            font=("Segoe UI", 10), bg=COLORS["bg_card"], fg=COLORS["accent_neon"],
            buttonbackground=COLORS["accent_green"], highlightthickness=0,
            textvariable=self.shutdown_warn_var,
        )
        self.shutdown_warn_spinner.pack(side=tk.LEFT, padx=(4, 4))

        tk.Label(self.shutdown_warn_row, text="minutos antes (0 = sin aviso)", font=("Segoe UI", 8),
                 fg=COLORS["text_secondary"], bg=COLORS["bg_panel"]).pack(side=tk.LEFT)

        shutdown_actions = tk.Frame(shutdown_frame, bg=COLORS["bg_panel"])
        shutdown_actions.pack(fill=tk.X, padx=10, pady=(0, 8))

        self.shutdown_now_btn = tk.Button(
            shutdown_actions, text="⏻ Apagar ahora (60 s)", font=("Segoe UI", 8),
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            command=self._on_shutdown_now_click,
        )
        self.shutdown_now_btn.pack(side=tk.LEFT)

        self.shutdown_postpone_btn = tk.Button(
            shutdown_actions, text=f"⏱ Posponer {DEFAULT_POSTPONE_MINUTES} min",
            font=("Segoe UI", 8),
            bg=COLORS["bg_card"], fg=COLORS["accent_neon"],
            command=self._on_shutdown_postpone_click,
        )
        self.shutdown_postpone_btn.pack(side=tk.LEFT, padx=(6, 0))

        self.shutdown_cancel_btn = tk.Button(
            shutdown_actions, text="✖ Cancelar apagado", font=("Segoe UI", 8),
            bg=COLORS["bg_card"], fg=COLORS["text_warning"],
            command=self._on_shutdown_cancel_click,
        )
        self.shutdown_cancel_btn.pack(side=tk.RIGHT)

        self.shutdown_mode_var.trace_add("write", self._on_shutdown_changed)
        self.shutdown_hour_var.trace_add("write", self._on_shutdown_changed)
        self.shutdown_minute_var.trace_add("write", self._on_shutdown_changed)
        self.shutdown_minutes_var.trace_add("write", self._on_shutdown_changed)
        self.shutdown_warn_var.trace_add("write", self._on_shutdown_changed)

        # ── Al iniciar ──────────────────────────────────────────────────
        start_frame = tk.Frame(
            features_frame, bg=COLORS["bg_panel"],
            highlightbackground=COLORS["border"], highlightthickness=1,
        )
        start_frame.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            start_frame, text="AL INICIAR", font=("Segoe UI", 8, "bold"),
            fg=COLORS["text_secondary"], bg=COLORS["bg_panel"],
        ).pack(anchor="w", padx=10, pady=(8, 2))

        tk.Checkbutton(
            start_frame, text="Iniciar con Windows", variable=self.auto_start_var,
            font=("Segoe UI", 9), fg=COLORS["text_primary"], bg=COLORS["bg_panel"],
            selectcolor=COLORS["bg_card"], activebackground=COLORS["bg_panel"],
            command=self._on_autostart_toggle_click,
        ).pack(anchor="w", padx=10)

        tk.Checkbutton(
            start_frame, text="Iniciar minimizado (solo el icono del tray)", variable=self.start_minimized_var,
            font=("Segoe UI", 9), fg=COLORS["text_primary"], bg=COLORS["bg_panel"],
            selectcolor=COLORS["bg_card"], activebackground=COLORS["bg_panel"],
            command=self._on_start_minimized_toggle_click,
        ).pack(anchor="w", padx=10)

        tk.Label(
            start_frame, text="Minimizado: la ventana no se abre hasta que hagas clic en el icono.",
            font=("Segoe UI", 7), fg=COLORS["text_secondary"], bg=COLORS["bg_panel"],
            wraplength=400, justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 8))

        # ─── Botón exportar ──────────────────────────────────────────────
        export_frame = tk.Frame(content, bg=COLORS["bg_dark"])
        export_frame.pack(fill=tk.X, padx=20, pady=(0, 5))

        tk.Button(
            export_frame, text="📊 Exportar CSV", font=("Segoe UI", 8),
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            command=self._on_export_click,
        ).pack(side=tk.LEFT)

        # ─── Footer ──────────────────────────────────────────────────────
        footer = tk.Frame(content, bg=COLORS["bg_dark"])
        footer.pack(fill=tk.X, side=tk.BOTTOM, pady=(5, 8))

        tk.Label(
            footer, text="Doble clic en el icono del tray para abrir/cerrar",
            font=("Segoe UI", 8),
            fg=COLORS["text_secondary"], bg=COLORS["bg_dark"],
        ).pack()

        self._update_shutdown_widgets()

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

    def _scroll_by(self, delta: int):
        """Desplaza el canvas acumulando el delta y traduciéndolo a píxeles.

        Así funciona tanto la rueda (múltiplos de 120) como el trackpad, que
        envía deltas pequeños y no se puede redondear a 0.
        """
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

    def _on_daily_goal_toggle_click(self):
        if self._on_daily_goal_toggle:
            self._on_daily_goal_toggle(self.daily_goal_enabled.get())

    def _on_goal_hours_change(self, *_args):
        try:
            val = int(self.daily_goal_hours_var.get())
            val = max(1, min(16, val))
            self._daily_goal_hours = val
            if self._on_daily_goal_change:
                self._on_daily_goal_change(val)
        except (ValueError, tk.TclError):
            pass

    def _on_pomodoro_toggle_click(self):
        if self._on_pomodoro_toggle:
            self._on_pomodoro_toggle(self.pomodoro_enabled.get())

    def _on_game_mode_toggle_click(self):
        if self._on_game_mode_toggle:
            self._on_game_mode_toggle(self.game_mode_enabled.get())

    def _on_screen_lock_toggle_click(self):
        if self._on_screen_lock_toggle:
            self._on_screen_lock_toggle(self.screen_lock_enabled.get())

    def _on_lock_hours_change(self, *_args):
        if self._suppress_callbacks:
            return
        try:
            val = int(self.lock_hours_var.get())
        except (ValueError, tk.TclError):
            return
        val = max(1, min(12, val))
        if self._on_screen_lock_hours_change:
            self._on_screen_lock_hours_change(val)

    # ─── Apagado automático e inicio ─────────────────────────────────────

    def _on_shutdown_toggle_click(self):
        # Activar/desactivar se aplica al instante
        self._update_shutdown_widgets()
        self._cancel_shutdown_emit()
        self._emit_shutdown_change()

    def _on_shutdown_changed(self, *_args):
        """Cambios en los controles: se espera a que el usuario termine.

        Sin esta espera, escribir '30' en el Spinbox dispararía un aviso por
        cada dígito (con su notificación y su sonido).
        """
        if self._suppress_callbacks:
            return
        self._update_shutdown_widgets()
        if not self.root:
            self._emit_shutdown_change()
            return
        self._cancel_shutdown_emit()
        self._shutdown_emit_job = self.root.after(600, self._emit_shutdown_change)

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
        """Lee los controles y los normaliza a valores válidos."""

        def _int(var, default: int, low: int, high: int) -> int:
            try:
                return max(low, min(high, int(var.get())))
            except (ValueError, tk.TclError):
                return default

        hour = _int(self.shutdown_hour_var, 23, 0, 23)
        minute = _int(self.shutdown_minute_var, 0, 0, 59)
        return {
            "enabled": bool(self.shutdown_enabled.get()),
            "mode": SHUTDOWN_MODE_KEYS.get(self.shutdown_mode_var.get(), "hora"),
            "time": f"{hour:02d}:{minute:02d}",
            "minutes": _int(self.shutdown_minutes_var, 60, 1, 720),
            "warn_minutes": _int(self.shutdown_warn_var, 5, 0, 30),
        }

    def _update_shutdown_widgets(self):
        """Habilita solo los controles del modo activo."""
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

    def _on_shutdown_now_click(self):
        if self._on_shutdown_now:
            self._on_shutdown_now()

    def _on_shutdown_postpone_click(self):
        if self._on_shutdown_postpone:
            self._on_shutdown_postpone()

    def _on_shutdown_cancel_click(self):
        if self._on_shutdown_cancel:
            self._on_shutdown_cancel()

    def _on_autostart_toggle_click(self):
        if self._on_autostart_toggle:
            self._on_autostart_toggle(self.auto_start_var.get())

    def _on_start_minimized_toggle_click(self):
        if self._on_start_minimized_toggle:
            self._on_start_minimized_toggle(self.start_minimized_var.get())

    def set_shutdown_status(self, text: str):
        """Actualiza la etiqueta de estado del apagado programado."""
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
            self.lock_hours_var.set(str(settings.get("screen_lock_hours", 4)))
            self.shutdown_enabled.set(settings.get("shutdown_enabled", False))
            self.shutdown_mode_var.set(SHUTDOWN_MODE_LABELS.get(settings.get("shutdown_mode", "hora"), "Hora fija"))
            hour, _, minute = str(settings.get("shutdown_time", "23:00")).partition(":")
            self.shutdown_hour_var.set(hour or "23")
            self.shutdown_minute_var.set(minute or "00")
            self.shutdown_minutes_var.set(str(settings.get("shutdown_minutes", 60)))
            self.shutdown_warn_var.set(str(settings.get("shutdown_warn_minutes", 5)))
            self.auto_start_var.set(settings.get("auto_start", False))
            self.start_minimized_var.set(settings.get("start_minimized", True))
        finally:
            self._suppress_callbacks = False
        self._update_shutdown_widgets()

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
                self.status_var.set("⏸ Pausado")
                self.status_label.configure(fg=COLORS["text_warning"])
            else:
                self.status_var.set("● Activo")
                self.status_label.configure(fg=COLORS["accent_green_light"])

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
        self.progress_canvas.delete("all")
        w = self.progress_canvas.winfo_width()
        h = self.progress_canvas.winfo_height()
        if w <= 1:
            return

        # La barra mide la sesión actual contra el límite vigente: el bloqueo
        # de pantalla si está activo, o la meta diaria como referencia si no.
        if self.settings.get("screen_lock_enabled", False):
            reference_hours = self.settings.get("screen_lock_hours", 4)
        else:
            reference_hours = self.settings.get("daily_goal_hours", 8)
        reference_hours = max(1, reference_hours)
        max_seconds = reference_hours * 3600
        progress = min(current_seconds / max_seconds, 1.0)
        fill_width = int(w * progress)

        if progress < 0.5:
            color = COLORS["progress_fill"]
        elif progress < 0.75:
            color = COLORS["progress_warning"]
        else:
            color = COLORS["progress_danger"]

        self.progress_canvas.create_rectangle(0, 0, w, h, fill=COLORS["progress_bg"], outline="")

        if fill_width > 0:
            for i in range(0, fill_width, 2):
                ratio = i / w
                if ratio < progress * 0.7:
                    c = color
                else:
                    c = COLORS["accent_green_light"] if color == COLORS["progress_fill"] else color
                self.progress_canvas.create_rectangle(i, 2, i + 2, h - 2, fill=c, outline="")

        pct = int(progress * 100)
        formatted_current = self.logger.format_seconds(current_seconds)
        self.progress_canvas.create_text(
            w // 2, h // 2,
            text=f"{pct}% de sesión ({formatted_current} / {reference_hours}h)",
            fill=COLORS["text_primary"],
            font=("Segoe UI", 8, "bold"),
        )

    def _draw_goal(self, total_seconds: int):
        self.goal_canvas.delete("all")
        w = self.goal_canvas.winfo_width()
        h = self.goal_canvas.winfo_height()
        if w <= 1:
            return

        goal_hours = self._daily_goal_hours if hasattr(self, "_daily_goal_hours") else 8
        goal_seconds = goal_hours * 3600
        progress = min(total_seconds / goal_seconds, 1.0)
        fill_width = int(w * progress)

        if progress < 0.5:
            color = COLORS["progress_fill"]
        elif progress < 0.8:
            color = COLORS["progress_warning"]
        else:
            color = COLORS["progress_danger"]

        self.goal_canvas.create_rectangle(0, 0, w, h, fill=COLORS["progress_bg"], outline="")
        if fill_width > 0:
            self.goal_canvas.create_rectangle(0, 0, fill_width, h, fill=color, outline="")

        pct = int(progress * 100)
        self.goal_canvas.create_text(
            w // 2, h // 2,
            text=f"{pct}% — Meta: {goal_hours}h",
            fill=COLORS["text_primary"],
            font=("Segoe UI", 7, "bold"),
        )
        self.daily_goal_var.set(f"{total_seconds // 3600}h {(total_seconds % 3600) // 60}m / {goal_hours}h")

    def set_daily_goal(self, hours: int):
        self._daily_goal_hours = hours

    def _draw_week_chart(self):
        try:
            self.week_canvas.delete("all")
            w = self.week_canvas.winfo_width()
            h = self.week_canvas.winfo_height()
            if w <= 1:
                return

            week_stats = self.logger.get_week_stats()
            days = list(reversed(list(week_stats.items())))
            if not days:
                return
            max_val = max((v for _, v in days), default=1) or 1
            bar_width = max(20, (w - 40) // 7 - 5)

            from datetime import date

            day_names = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]

            for i, (day_str, seconds) in enumerate(days):
                x = 20 + i * (bar_width + 5)
                bar_h = max(2, int((seconds / max_val) * (h - 20)))
                y_top = h - 15 - bar_h
                y_bottom = h - 15

                color = COLORS["accent_green"] if seconds > 0 else COLORS["progress_bg"]
                self.week_canvas.create_rectangle(x, y_top, x + bar_width, y_bottom, fill=color, outline="")

                try:
                    d = date.fromisoformat(day_str)
                    label = day_names[d.weekday()]
                except (ValueError, IndexError):
                    label = day_str[-2:]

                self.week_canvas.create_text(
                    x + bar_width // 2, h - 5,
                    text=label, fill=COLORS["text_secondary"],
                    font=("Segoe UI", 7),
                )
        except Exception:
            pass

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
            if unit == "Segundos":
                seconds = val
            elif unit == "Minutos":
                seconds = val * 60
            else:
                seconds = val * 3600
            if self._on_interval_change:
                self._on_interval_change(seconds)
            try:
                overlay_val = int(self.overlay_var.get())
                overlay_val = max(2, min(30, overlay_val))
            except (ValueError, tk.TclError):
                overlay_val = 8
            if self._on_overlay_change:
                self._on_overlay_change(overlay_val)
        except (ValueError, tk.TclError):
            pass

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
