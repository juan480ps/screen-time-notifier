"""Diálogos auxiliares de la interfaz."""

import tkinter as tk

from screentime.theme import COLORS


class IntervalDialog:
    """Diálogo para configurar el intervalo de notificaciones."""

    def __init__(self, parent, current_interval_seconds: int):
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Configurar intervalo")
        self.dialog.geometry("320x240")
        self.dialog.configure(bg=COLORS["bg_dark"])
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 160
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 120
        self.dialog.geometry(f"+{x}+{y}")

        tk.Label(
            self.dialog, text="Intervalo de notificación",
            font=("Segoe UI", 11, "bold"),
            fg=COLORS["text_primary"], bg=COLORS["bg_dark"],
        ).pack(pady=(15, 5))

        tk.Label(
            self.dialog, text="Cada cuánto recibir aviso:",
            font=("Segoe UI", 9),
            fg=COLORS["text_secondary"], bg=COLORS["bg_dark"],
        ).pack()

        input_frame = tk.Frame(self.dialog, bg=COLORS["bg_dark"])
        input_frame.pack(pady=10)

        self.spinner = tk.Spinbox(
            input_frame, from_=1, to=999, increment=1, width=6,
            font=("Segoe UI", 13),
            bg=COLORS["bg_card"], fg=COLORS["accent_neon"],
            buttonbackground=COLORS["accent_green"], highlightthickness=0,
        )
        self.spinner.pack(side=tk.LEFT, padx=(0, 8))

        if current_interval_seconds % 3600 == 0 and current_interval_seconds >= 3600:
            default_unit = "Horas"
            default_val = current_interval_seconds // 3600
        elif current_interval_seconds % 60 == 0 and current_interval_seconds >= 60:
            default_unit = "Minutos"
            default_val = current_interval_seconds // 60
        else:
            default_unit = "Segundos"
            default_val = current_interval_seconds

        self.unit_var = tk.StringVar(value=default_unit)
        self.unit_menu = tk.OptionMenu(
            input_frame, self.unit_var,
            "Segundos", "Minutos", "Horas",
        )
        self.unit_menu.configure(
            font=("Segoe UI", 9),
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            activebackground=COLORS["accent_green"], activeforeground="white",
            highlightthickness=0, width=8,
        )
        self.unit_menu["menu"].configure(
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            activebackground=COLORS["accent_green"],
        )
        self.unit_menu.pack(side=tk.LEFT)

        self.spinner.delete(0, tk.END)
        self.spinner.insert(0, str(default_val))

        self.unit_var.trace_add("write", self._on_unit_change)

        btn_frame = tk.Frame(self.dialog, bg=COLORS["bg_dark"])
        btn_frame.pack(pady=10)

        tk.Button(
            btn_frame, text="Aceptar",
            font=("Segoe UI", 9, "bold"),
            bg=COLORS["accent_green"], fg="white",
            width=10, command=self._on_accept,
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame, text="Cancelar",
            font=("Segoe UI", 9),
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            width=10, command=self._on_cancel,
        ).pack(side=tk.LEFT, padx=5)

    def _on_unit_change(self, *_args):
        unit = self.unit_var.get()
        self.spinner.config(from_=1)
        if unit == "Segundos":
            self.spinner.config(to=59)
        elif unit == "Minutos":
            self.spinner.config(to=120)
        elif unit == "Horas":
            self.spinner.config(to=12)

    def _on_accept(self):
        try:
            val = int(self.spinner.get())
            if val < 1:
                return
            unit = self.unit_var.get()
            if unit == "Segundos":
                self.result = val
            elif unit == "Minutos":
                self.result = val * 60
            elif unit == "Horas":
                self.result = val * 3600
            self.dialog.destroy()
        except ValueError:
            pass

    def _on_cancel(self):
        self.dialog.destroy()

    def show(self):
        self.dialog.wait_window()
        return self.result
