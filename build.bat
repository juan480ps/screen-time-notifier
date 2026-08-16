@echo off
echo ========================================
echo  Screen Time Notifier - Build Script
echo ========================================
echo.

call venv\Scripts\activate.bat

pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Instalando PyInstaller en el venv...
    pip install pyinstaller
)

echo Creando ejecutable...
pyinstaller --noconfirm --onefile --noconsole --name="ScreenTimeNotifier" ^
    --icon="assets\icon.ico" ^
    --add-data="assets;assets" ^
    --hidden-import=pystray._win32 ^
    --hidden-import=PIL ^
    --hidden-import=pygame ^
    src\screentime\app.py

echo.
echo ========================================
echo  Build completado!
echo  Ejecutable en: dist\ScreenTimeNotifier.exe
echo ========================================
pause
