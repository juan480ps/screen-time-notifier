"""Lógica de notificaciones de la aplicación."""

import os
import random
import threading
from typing import Callable, Optional

from screentime.config import NOTIFY_SOUND

NORMAL_MESSAGES = [
    "🎮 ¡Hey! Ya llevas {time} frente a la pantalla. ¿Todo bien?",
    "⏰ Aviso: llevas {time} conectado. ¡Recuerda descansar!",
    "👀 Han pasado {time}. ¡Estira las piernas!",
    "🖥️ Llevas {time} en la computadora. ¡Haz una pausa!",
    "☕ Ya son {time}. ¿Qué tal un cafecito y estirar el cuerpo?",
    "🌿 {time} frente a la pantalla. ¡Mira algo lejos un momento!",
    "💪 Llevas {time} trabajando. ¡Tu cuerpo lo agradecerá si descansas!",
    "🎯 {time} de sesión. ¡Un descanso corto mejora la productividad!",
    "🧘 Han pasado {time}. Respira profundo y estira los hombros.",
    "🌞 Llevas {time} conectado. ¡Sal a tomar un poco de aire!",
]

WARNING_MESSAGES = [
    "⚠️ Llevas {time} conectado. ¡Es hora de un descanso!",
    "🔴 ¡AVISO! {time} frente a la pantalla. Descansa ya.",
    "🛑 {time} sin parar. ¡Tu salud visual te necesita!",
    "⚠️ ¡Alerta! Llevas {time} conectado. Levántate y mueve el cuerpo.",
    "⚡ {time} de uso continuo. ¡Riesgo de fatiga visual! Descansa.",
    "🚨 ¡Importante! {time} en pantalla. Haz una pausa prolongada.",
    "⚠️ {time} conectado. ¡El exceso de pantalla afecta tu sueño!",
    "🔴 Llevas {time}. ¡Tu postura sufre! Estira la espalda.",
]


class ScreenTimeNotifier:
    """Gestiona el sistema de notificaciones por tiempo."""

    def __init__(self):
        self._timer: Optional[threading.Timer] = None
        self._interval_seconds: int = 1800
        self._paused: bool = False
        self._running: bool = False
        self._notification_callback: Optional[Callable] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    def set_interval_seconds(self, seconds: int):
        if seconds > 0:
            self._interval_seconds = seconds

    def set_notification_callback(self, callback: Callable):
        self._notification_callback = callback

    def start(self):
        if self._running:
            return
        self._running = True
        self._paused = False
        self._schedule_next()

    def stop(self):
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def pause(self):
        self._paused = True

    def resume(self):
        if self._paused:
            self._paused = False
            if self._running:
                self._schedule_next()

    def _schedule_next(self):
        if not self._running or self._paused:
            return
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self._interval_seconds, self._on_timer)
        self._timer.daemon = True
        self._timer.start()

    def _on_timer(self):
        if not self._running or self._paused:
            return
        if self._notification_callback:
            self._notification_callback()
        self._schedule_next()

    def get_random_message(self, time_str: str, is_warning: bool = False) -> str:
        pool = WARNING_MESSAGES if is_warning else NORMAL_MESSAGES
        return random.choice(pool).format(time=time_str)

    @staticmethod
    def _init_mixer():
        """Inicializa pygame mixer una sola vez."""
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            return True
        except Exception:
            return False

    @classmethod
    def play_notification_sound(cls):
        """Reproduce sonido en hilo background para no bloquear la UI."""
        def _play():
            try:
                if os.path.exists(NOTIFY_SOUND):
                    import pygame
                    cls._init_mixer()
                    pygame.mixer.music.load(NOTIFY_SOUND)
                    pygame.mixer.music.set_volume(0.8)
                    pygame.mixer.music.play()
                else:
                    import winsound
                    winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                try:
                    import winsound
                    winsound.MessageBeep(winsound.MB_OK)
                except Exception:
                    pass

        t = threading.Thread(target=_play, daemon=True)
        t.start()
