# Screen Time Notifier

Monitor de tiempo en pantalla para Windows con notificaciones estilo Xbox.

## Capturas

> TODO: agregar screenshots de la interfaz

## Funcionalidades

- **Contador de tiempo en sesion** — Mide el tiempo de uso del PC en tiempo real.
- **Notificaciones toast** — Cada X tiempo (configurable) muestra una notificacion con sonido Xbox.
- **Icono en bandeja del sistema** — Acceso rapido a todas las funciones.
- **Historial diario** — Registra y muestra estadisticas de uso por dia y semana.
- **Meta diaria** — Limite configurable de horas diarias con barra de progreso.
- **Modo Pomodoro** — Ciclos trabajo/descanso con temporizador visual.
- **Modo juego** — Pausa automatica de notificaciones en pantalla completa (fullscreen).
- **Bloqueo de pantalla** — Overlay de descanso despues de X horas configurables.
- **Exportar CSV** — Historial de uso exportable a Excel/Google Sheets.
- **Recordar ventana** — Guarda y restaura el tamano/posicion de la ventana.
- **Inicio automatico** — Opcion para iniciar con Windows.
- **Sonido Xbox** — Notificacion con sonido original de Xbox Game Bar.

## Demo

```
# Ejecutar desde codigo fuente
python -m screentime

# O usar el script rapido
run.bat
```

## Instalacion

### Requisitos previos

- Python 3.10 o superior
- Windows 10 / Windows 11

### Desde codigo fuente

```bash
# Clonar el repositorio
git clone https://github.com/TU_USUARIO/screen-time-notifier.git
cd screen-time-notifier

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
python -m screentime
```

### Ejecutable (sin Python)

Descarga `ScreenTimeNotifier.exe` desde [Releases](https://github.com/TU_USUARIO/screen-time-notifier/releases) y ejecutalo directamente. No requiere instalacion.

Los datos se guardan en `%LOCALAPPDATA%\Screen Time Notifier\`.

## Estructura del proyecto

```
screen-time-notifier/
├── pyproject.toml                # Metadata del proyecto
├── requirements.txt              # Dependencias de produccion
├── requirements-dev.txt          # Dependencias de desarrollo
├── .gitignore
├── README.md
├── run.bat                       # Ejecutar desde codigo fuente
├── build.bat                     # Generar ejecutable .exe
├── assets/
│   ├── icon.ico                  # Icono de la aplicacion
│   └── sounds/
│       └── notify.mp3            # Sonido de notificacion Xbox
└── src/
    └── screentime/               # Paquete principal
        ├── __init__.py           # Version y metadata
        ├── __main__.py           # Entry point: python -m screentime
        ├── app.py                # Orquestador principal (ScreenTimeApp)
        ├── config.py             # Configuraciones y persistencia JSON
        ├── logger.py             # Registro de uso y estadisticas
        ├── notifier.py           # Timer de notificaciones + sonido
        ├── gui.py                # Interfaz grafica (tkinter + canvas)
        ├── tray_icon.py          # System tray (pystray)
        ├── pomodoro.py           # Temporizador Pomodoro
        └── fullscreen_detector.py # Deteccion de pantalla completa (Win32)
```

## Uso

1. Al iniciar, la aplicacion aparece en la **bandeja del sistema** (icono verde con "S").
2. Cada intervalo recibirás una notificacion con tu tiempo de uso y sonido Xbox.
3. Haz **doble clic** en el icono del tray para abrir la ventana principal.
4. Haz **clic derecho** en el icono para ver el menu de opciones.

### Menu del tray

| Opcion | Descripcion |
|--------|-------------|
| Ver tiempo actual | Abre/cierra la ventana principal |
| Reiniciar contador | Pone el contador a cero y guarda la sesion |
| Pausar/Reanudar | Pausa o reanuda las notificaciones |
| Configurar intervalo | Cambia el intervalo entre notificaciones |
| Iniciar con Windows | Activa/desactiva el inicio automatico |
| Salir | Cierra la aplicacion |

### Configuracion

Todas las opciones son configurables desde la ventana principal:

- **Intervalo** — Segundos, minutos u horas entre notificaciones.
- **Popup visible** — Duracion del overlay en pantalla (2-30 seg).
- **Meta diaria** — Horas maximas por dia con barra de progreso.
- **Pomodoro** — Minutos de trabajo/descanso y ciclos.
- **Modo juego** — Pausa automatica en fullscreen.
- **Bloqueo** — Horas antes de mostrar overlay de descanso.

Las configuraciones se guardan en `%LOCALAPPDATA%\Screen Time Notifier\settings.json`.

## Desarrollo

```bash
# Instalar en modo editable con dependencias de desarrollo
pip install -e ".[dev]"

# Linting
ruff check src/

# Ejecutar
python -m screentime

# Generar ejecutable
build.bat
```

## Build

```bash
# Genera dist/ScreenTimeNotifier.exe (~25MB, standalone)
build.bat
```

El ejecutable incluye Python, todas las librerias y assets empaquetados. Funciona en cualquier maquina Windows sin necesidad de instalar nada.

## Tecnologias

- **Python 3.12** — Lenguaje principal
- **tkinter** — Interfaz grafica
- **pystray** — System tray icon
- **Pillow** — Generacion de iconos
- **pygame** — Reproduccion de sonido
- **PyInstaller** — Empaquetado como .exe standalone
- **Win32 API** — Deteccion de fullscreen y registro de Windows

## Licencia

MIT
