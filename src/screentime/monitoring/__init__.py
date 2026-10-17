"""Monitoreo de recursos in-app (sampler asíncrono opcional).

Se controla por entorno:
- SCREENTIME_MONITOR          1/0 (def. 1: panel visible)
- SCREENTIME_MONITOR_INTERVAL segundos entre muestras (0.5-60, def. 2.0)
- SCREENTIME_MONITOR_HISTORY  puntos de historial (10-3600, def. 60)
"""

from __future__ import annotations

from screentime.config_env import get_bool, get_float, get_int
from screentime.logging_setup import get_logger

__all__ = ["create_sampler"]


def create_sampler():
    """Crea un MetricsSampler si el flag está activo. Nunca lanza."""
    if not get_bool("SCREENTIME_MONITOR", True):
        return None
    try:
        from screentime.monitoring.metrics import MetricsSampler

        return MetricsSampler(
            interval=get_float("SCREENTIME_MONITOR_INTERVAL", 2.0, 0.5, 60.0),
            history=get_int("SCREENTIME_MONITOR_HISTORY", 60, 10, 3600),
            gpu_interval=get_float("SCREENTIME_MONITOR_GPU_INTERVAL", 5.0, 1.0, 60.0),
            logger=get_logger("monitoring"),
        )
    except Exception:
        get_logger("monitoring").exception("No se pudo inicializar el monitoreo de recursos")
        return None
