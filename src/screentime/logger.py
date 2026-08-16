"""Sistema de registro y historial de uso."""

import json
import os
from datetime import datetime, date, timedelta
from typing import Optional

from screentime.config import HISTORY_FILE, DATA_DIR


class UsageLogger:
    """Gestiona el registro de sesiones de uso del PC."""

    def __init__(self):
        self._ensure_file()
        self.session_start = datetime.now()
        self.total_pause_seconds = 0.0
        self._pause_start: Optional[datetime] = None
        self._is_paused = False

    def _ensure_file(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(HISTORY_FILE):
            self._save_data({"daily_sessions": {}, "total_usage_seconds": 0})

    def _load_data(self) -> dict:
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"daily_sessions": {}, "total_usage_seconds": 0}

    def _save_data(self, data: dict):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except IOError:
            pass

    def pause(self):
        if not self._is_paused:
            self._is_paused = True
            self._pause_start = datetime.now()

    def resume(self):
        if self._is_paused and self._pause_start:
            self.total_pause_seconds += (datetime.now() - self._pause_start).total_seconds()
            self._is_paused = False
            self._pause_start = None

    def reset(self):
        self.session_start = datetime.now()
        self.total_pause_seconds = 0.0
        self._pause_start = None
        self._is_paused = False

    def get_elapsed_seconds(self) -> float:
        elapsed = (datetime.now() - self.session_start).total_seconds()
        paused = self.total_pause_seconds
        if self._is_paused and self._pause_start:
            paused += (datetime.now() - self._pause_start).total_seconds()
        return max(0, elapsed - paused)

    def get_elapsed_formatted(self) -> str:
        total_seconds = int(self.get_elapsed_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        parts = []
        if hours > 0:
            parts.append("1 hora" if hours == 1 else f"{hours} horas")
        if minutes > 0:
            parts.append("1 minuto" if minutes == 1 else f"{minutes} minutos")
        if seconds > 0 and hours == 0:
            parts.append("1 segundo" if seconds == 1 else f"{seconds} segundos")

        return " y ".join(parts) if parts else "0 segundos"

    def get_elapsed_short(self) -> str:
        total_seconds = int(self.get_elapsed_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def get_elapsed_minutes(self) -> float:
        return self.get_elapsed_seconds() / 60.0

    def save_session(self):
        data = self._load_data()
        today = date.today().isoformat()

        if today not in data["daily_sessions"]:
            data["daily_sessions"][today] = {"sessions": [], "total_seconds": 0}

        session_data = {
            "start": self.session_start.isoformat(),
            "end": datetime.now().isoformat(),
            "duration_seconds": int(self.get_elapsed_seconds()),
        }

        data["daily_sessions"][today]["sessions"].append(session_data)
        data["daily_sessions"][today]["total_seconds"] += session_data["duration_seconds"]
        data["total_usage_seconds"] += session_data["duration_seconds"]

        self._save_data(data)

    def get_today_stats(self) -> dict:
        data = self._load_data()
        today = date.today().isoformat()

        if today not in data["daily_sessions"]:
            return {
                "total_seconds": 0,
                "sessions_count": 0,
                "current_session_seconds": int(self.get_elapsed_seconds()),
            }

        day_data = data["daily_sessions"][today]
        return {
            "total_seconds": day_data["total_seconds"] + int(self.get_elapsed_seconds()),
            "sessions_count": len(day_data["sessions"]),
            "current_session_seconds": int(self.get_elapsed_seconds()),
        }

    def get_week_stats(self) -> dict:
        data = self._load_data()
        today = date.today()
        week_data = {}

        for i in range(7):
            day = (today - timedelta(days=i)).isoformat()
            if day in data["daily_sessions"]:
                week_data[day] = data["daily_sessions"][day]["total_seconds"]
            else:
                week_data[day] = 0

        return week_data

    def format_seconds(self, total_seconds: int) -> str:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes:02d}m"
        return f"{minutes}m"
