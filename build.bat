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
pyinstaller --noconfirm ScreenTimeNotifier.spec

echo.
echo ========================================
echo  Build completado!
echo  Ejecutable en: dist\ScreenTimeNotifier.exe
echo ========================================
pause
