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
- **Apagado automatico** — Programa el apagado del equipo a una hora fija (todos los dias) o con una cuenta atras, con aviso previo y opcion de cancelar.
- **Inicio minimizado** — Arranca solo en la bandeja del sistema para no interrumpir (opcional).
- **Exportar CSV** — Historial de uso exportable a Excel/Google Sheets.
- **Recordar ventana** — Guarda y restaura el tamano/posicion de la ventana.
- **Inicio automatico** — Opcion para iniciar con Windows.
- **Sonido Xbox** — Notificacion con sonido original de Xbox Game Bar.
- **Panel de recursos** — CPU, RAM y GPU en tiempo real dentro de la app (gauges + histórico).

## Demo

```
# Ejecutar desde codigo fuente
python -m screentime

# O usar el script rapido
run.bat
```

## Instalacion

### Requisitos previos

- Python 3.10 o superior. En Python 3.14 o superior se instala `pygame-ce` (fork compatible que expone el mismo modulo `pygame`) porque `pygame` no publica ruedas para esas versiones.
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
│       └── notify.mp3            # Sonido de notificación Xbox
├── tests/                        # Tests (unittest)
│   ├── test_units.py
│   ├── test_gui_smoke.py
│   └── test_monitoring.py
└── src/
    └── screentime/               # Paquete principal
        ├── __init__.py           # Version y metadata
        ├── __main__.py           # Entry point: python -m screentime
        ├── app.py                # Orquestador principal (ScreenTimeApp)
        ├── config.py             # Configuraciones y persistencia JSON
        ├── config_env.py         # Config por entorno (tipada/validada)
        ├── logging_setup.py      # Logging estructurado con rotacion
        ├── logger.py             # Registro de uso y estadisticas
        ├── notifier.py           # Timer de notificaciones + sonido
        ├── gui.py                # Interfaz grafica (tkinter + canvas)
        ├── theme.py              # Design tokens (colores, fuentes)
        ├── dialogs.py            # Dialogos auxiliares
        ├── tray_icon.py          # System tray (pystray)
        ├── pomodoro.py           # Temporizador Pomodoro
        ├── fullscreen_detector.py # Deteccion de pantalla completa (Win32)
        ├── shutdown.py           # Apagado automatico programado (shutdown.exe)
        ├── ui/                   # Widgets y toast animado
        └── monitoring/           # Muestreo CPU/RAM/GPU (in-app)
```

## Uso

1. Al iniciar, la aplicacion aparece en la **bandeja del sistema** (icono verde con "S").
   Por defecto arranca **minimizada**; desmarca "Iniciar minimizado" en la tarjeta *AL INICIAR* si prefieres que la ventana se abra al arrancar.
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
| Iniciar minimizado | Activa/desactiva que la ventana se abra al arrancar |
| Activar apagado automatico | Programa o desactiva el apagado segun la configuracion guardada |
| Apagar ahora (60 s) | Apaga el equipo en 60 segundos (cancelable) |
| Posponer apagado (10 min) | Retrasa el apagado pendiente sin desactivarlo (solo si hay uno programado) |
| Cancelar apagado | Aborta el apagado pendiente y desactiva la programacion |
| Salir | Cierra la aplicacion |

### Configuracion

Todas las opciones son configurables desde la ventana principal:

- **Intervalo** — Segundos, minutos u horas entre notificaciones.
- **Popup visible** — Duracion del overlay en pantalla (2-30 seg).
- **Meta diaria** — Horas maximas por dia con barra de progreso.
- **Pomodoro** — Minutos de trabajo/descanso y ciclos.
- **Modo juego** — Pausa automatica en fullscreen.
- **Bloqueo** — Minutos u horas antes de mostrar el overlay de descanso.
- **Apagado automatico** — Hora fija diaria o cuenta atras, y minutos de aviso previo.
- **Inicio** — Arrancar con Windows y arrancar minimizado.

Las configuraciones se guardan en `%LOCALAPPDATA%\Screen Time Notifier\settings.json`.

## Apagado automatico

En la tarjeta **APAGADO AUTOMATICO** de la ventana principal:

- **Hora fija** — Se repite todos los dias a la hora indicada. Si la hora ya paso, se programa para el dia siguiente.
- **Cuenta atras** — Apaga una sola vez, X minutos u horas despues de activarlo (hasta 720 min).
- **Avisar** — Notificacion con sonido N minutos antes (0 = sin aviso previo).
- La **cuenta atras se muestra en vivo**: la etiqueta de estado de la ventana y el titulo del icono del tray se actualizan cada segundo con el tiempo restante (por ejemplo `Apagado en 29m 41s`).
- **Posponer 10 min** (boton de la ventana y opcion del tray) retrasa el apagado pendiente sin desactivarlo; el aviso previo vuelve a armarse si aun falta mas que el umbral.
- Al llegar la hora, Windows recibe el apagado con **60 segundos de margen**, cancelable desde el icono del tray.
- **Cancelar apagado** ejecuta `shutdown /a` y deja la programacion desactivada.
- Si cierras la aplicacion con un apagado pendiente, se cancela para no apagar el equipo sin querer.

## Panel de recursos

Tarjeta **RECURSOS** dentro de la ventana principal (columna izquierda):
gauges de CPU, RAM y GPU + histórico tipo time-series. Muestrea CPU/RAM con
`psutil` y GPU vía los contadores de rendimiento de Windows (cualquier GPU:
AMD/Intel/NVIDIA; `nvidia-smi` como alternativa) en un hilo daemon con
throttling configurable; la UI solo lee el último snapshot, sin bloquearse.

| Variable | Defecto | Descripcion |
|----------|---------|-------------|
| `SCREENTIME_MONITOR` | `1` | Muestra/oculta el panel (`0` lo desactiva) |
| `SCREENTIME_MONITOR_INTERVAL` | `2.0` | Segundos entre muestras CPU/RAM (0.5–60) |
| `SCREENTIME_MONITOR_GPU_INTERVAL` | `5.0` | Segundos entre muestras de GPU (1–60) |
| `SCREENTIME_MONITOR_HISTORY` | `60` | Puntos de historial (10–3600) |
| `SCREENTIME_HISTORY_RETENTION_DAYS` | `365` | Retención del historial (30–3650) |
| `SCREENTIME_LOG_LEVEL` | `INFO` | Nivel de logging estructurado |

**Rendimiento:** el historial vive en caché en memoria (sin lecturas de disco
por segundo), se poda por retención, la UI no redibuja con la ventana oculta,
la GPU se muestrea cada 5 s y el update-check automático se cachea 24 h.

Si Windows no expone el contador de GPU, se muestra `N/D` sin errores.

## Desarrollo

```bash
# Instalar en modo editable con dependencias de desarrollo
pip install -e ".[dev]"

# Linting
ruff check src/ tests/

# Tests
python -m unittest discover -s tests

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
- **psutil** — Metricas de CPU y RAM
- **pygame** / **pygame-ce** — Reproduccion de sonido
- **PyInstaller** — Empaquetado como .exe standalone
- **Win32 API** — Deteccion de fullscreen y registro de Windows

## Licencia

MIT
