"""Sistema de auto-actualizacion desde GitHub Releases."""

import json
import os
import sys
import subprocess
import tempfile
import urllib.request
import urllib.error
from typing import Optional

from screentime import __version__

GITHUB_REPO = "juan480ps/screen-time-notifier"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
EXE_NAME = "ScreenTimeNotifier.exe"


def _get_exe_path() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(sys.argv[0])


def _get_exe_dir() -> str:
    return os.path.dirname(_get_exe_path())


def _parse_version(v: str) -> tuple:
    try:
        parts = v.strip().lstrip("v").split(".")
        return tuple(int(p) for p in parts)
    except (ValueError, AttributeError):
        return (0, 0, 0)


def _log(msg: str):
    try:
        from screentime.config import DATA_DIR
        log_path = os.path.join(DATA_DIR, "app.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
    except Exception:
        pass


def check_for_update() -> Optional[dict]:
    """Retorna dict con info de update, True si esta actualizado, o None si hay error."""
    try:
        _log(f"[Update] Consultando {GITHUB_API}")
        req = urllib.request.Request(GITHUB_API, headers={"Accept": "application/vnd.github.v3+json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        remote_tag = data.get("tag_name", "")
        _log(f"[Update] Remota: {remote_tag} | Local: v{__version__}")

        remote_ver = _parse_version(remote_tag)
        local_ver = _parse_version(__version__)

        if remote_ver <= local_ver:
            _log(f"[Update] Ya esta actualizado.")
            return True

        exe_asset = None
        for asset in data.get("assets", []):
            if asset["name"] == EXE_NAME:
                exe_asset = asset
                break

        if not exe_asset:
            _log(f"[Update] No se encontro asset {EXE_NAME} en la release.")
            return True

        _log(f"[Update] Nueva version encontrada: {remote_tag}")
        return {
            "version": remote_tag,
            "name": data.get("name", remote_tag),
            "body": data.get("body", ""),
            "download_url": exe_asset["browser_download_url"],
            "size": exe_asset.get("size", 0),
        }
    except urllib.error.URLError as e:
        _log(f"[Update] Error de red: {e}")
        return None
    except Exception as e:
        _log(f"[Update] Error inesperado: {e}")
        return None


def _create_update_batch(exe_path: str, new_exe_path: str) -> str:
    bat_path = os.path.join(tempfile.gettempdir(), "screentime_update.bat")
    bat_content = f'''@echo off
echo Screen Time Notifier - Actualizando...
timeout /t 5 /nobreak >nul
:retry
del "{exe_path}" 2>nul
if exist "{exe_path}" (
    timeout /t 2 /nobreak >nul
    goto retry
)
move /y "{new_exe_path}" "{exe_path}" >nul 2>&1
if errorlevel 1 (
    echo Error al reemplazar el ejecutable.
    timeout /t 5 /nobreak >nul
) else (
    echo Actualizacion completada. Iniciando...
    start "" "{exe_path}"
)
del "%~f0"
'''
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)
    return bat_path


def download_and_update(info: dict, on_progress=None) -> bool:
    try:
        exe_dir = _get_exe_dir()
        new_exe_path = os.path.join(exe_dir, f"{EXE_NAME}.new")

        req = urllib.request.Request(info["download_url"])
        with urllib.request.urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 1024 * 256

            with open(new_exe_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress and total > 0:
                        on_progress(downloaded, total)

        bat_path = _create_update_batch(_get_exe_path(), new_exe_path)
        subprocess.Popen(["cmd", "/c", bat_path], creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except Exception as e:
        _log(f"[Update] Error descarga: {e}")
        return False
