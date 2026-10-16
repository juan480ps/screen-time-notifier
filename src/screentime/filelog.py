"""Log a archivo con rotacion simple por tamano."""

import os

from screentime.config import DATA_DIR

LOG_FILE = os.path.join(DATA_DIR, "app.log")
_MAX_BYTES = 1024 * 1024


def append_log(msg: str) -> None:
    """Añade una linea al log, rotando a .1 si supera el tamaño maximo."""
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > _MAX_BYTES:
            try:
                os.replace(LOG_FILE, LOG_FILE + ".1")
            except OSError:
                pass
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
    except OSError:
        pass
