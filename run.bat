@echo off
echo Iniciando Screen Time Notifier...
call venv\Scripts\activate.bat

REM Instalar paquete en modo editable si no está instalado
pip show screen-time-notifier >nul 2>&1
if errorlevel 1 (
    echo Instalando paquete...
    pip install -e .
)

python -m screentime
