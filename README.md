```
██████╗ ███████╗ ██████╗██╗   ██╗ ██████╗██╗     ███████╗██████╗    ██╗   ██╗██╗███████╗██╗ ██████╗ ███╗   ██╗
██╔══██╗██╔════╝██╔════╝╚██╗ ██╔╝██╔════╝██║     ██╔════╝██╔══██╗   ██║   ██║██║██╔════╝██║██╔═══██╗████╗  ██║
██████╔╝█████╗  ██║      ╚████╔╝ ██║     ██║     █████╗  ██████╔╝   ██║   ██║██║███████╗██║██║   ██║██╔██╗ ██║
██╔══██╗██╔══╝  ██║       ╚██╔╝  ██║     ██║     ██╔══╝  ██╔══██╗   ╚██╗ ██╔╝██║╚════██║██║██║   ██║██║╚██╗██║
██║  ██║███████╗╚██████╗   ██║   ╚██████╗███████╗███████╗██║  ██║    ╚████╔╝ ██║███████║██║╚██████╔╝██║ ╚████║
╚═╝  ╚═╝╚══════╝ ╚═════╝   ╚═╝    ╚═════╝╚══════╝╚══════╝╚═╝  ╚═╝     ╚═══╝  ╚═╝╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝
```

# RecyclerVision — Sistema Inteligente de Reciclaje

**YOLOv11 · PySide6 · OpenCV · ESP32 · Clasificación de Residuos en Tiempo Real**

---

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.6+-41CD52?style=flat-square&logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![YOLOv11](https://img.shields.io/badge/YOLOv11-Ultralytics-00FFFF?style=flat-square)](https://github.com/ultralytics/ultralytics)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.9+-5C3EE8?style=flat-square&logo=opencv&logoColor=white)](https://opencv.org/)
[![ESP32](https://img.shields.io/badge/ESP32-Serial_UART-E7352C?style=flat-square&logo=espressif)](https://www.espressif.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

---

## ¿Qué es esto?

**RecyclerVision** es un sistema completo de visión por computadora para la **clasificación automática de residuos reciclables** (botellas PET y latas), desarrollado en la **Universidad Anáhuac Mayab**. El proyecto integra dos componentes principales en un solo ecosistema:

Una **aplicación de escritorio Qt (PySide6)** con tres pestañas funcionales: captura de dataset con cámara en tiempo real, detección con modelo YOLO entrenado, y configuración de hardware (cámara + ESP32). Todo corre a ~30 fps con inferencia en hilo separado para no bloquear la UI.

Un **módulo de comunicación Serial hacia ESP32** que envía comandos UART para controlar la maquinaria física: banda transportadora, actuador lineal (compuerta) y carriles de clasificación. El protocolo está diseñado para ser robusto y extensible.

El flujo completo es: **capturar dataset** con la misma cámara de producción → **etiquetar en Roboflow** → **entrenar YOLOv11** en GPU → **desplegar el modelo `.pt`** directamente en la aplicación → **clasificar en tiempo real** y actuar sobre la banda.

---

## Características

### 🖥️ Aplicación Python / PySide6

|  | Función | Detalle |
|---|---|---|
| 📸 | Captura de dataset | Ráfaga automática configurable: lote, clase, cantidad e intervalo en ms |
| 🧠 | Inferencia YOLO | YOLOWorker en QThread independiente — umbral de confianza e IOU ajustables en vivo |
| 🎥 | CameraThread | Captura de frames a ~30 fps en hilo propio — señal `frame_ready` a todos los tabs |
| 🔌 | SerialManager | Lector no bloqueante en QThread interno — envío de comandos UART al ESP32 |
| ⚙️ | Tab Configuración | Conectar/desconectar cámara y puerto serial desde la UI |
| 📸 | Tab Captura Dataset | Vista en vivo + ráfaga automática + estructura de carpetas por lote y clase |
| 🤖 | Tab Detección | Cargar modelo `.pt`, ajustar parámetros, log en pantalla, control manual de la banda |
| 🛑 | Cierre limpio | `MainWindow` detiene todos los hilos al cerrar — sin procesos huérfanos |
| 🖼️ | HiDPI | Soporte `PassThrough` para pantallas de alta densidad (Retina, 4K) |

### 🔩 Control ESP32 (Protocolo Serial)

|  | Comando | Función |
|---|---|---|
| ▶️ | `BELT:START` | Arranca la banda transportadora |
| ⏹️ | `BELT:STOP` | Para la banda |
| ⚡ | `BELT:SPEED:80` | Velocidad variable 0–100 |
| 🔓 | `GATE:OPEN` | Abre el actuador lineal (compuerta) |
| 🔒 | `GATE:CLOSE` | Cierra el actuador lineal |
| ♻️ | `SORT:0` | Desvía al carril de descarte / ninguno |
| 🍶 | `SORT:1` | Desvía al carril de botellas |
| 🥫 | `SORT:2` | Desvía al carril de latas |
| 🚨 | `E_STOP` | Paro de emergencia inmediato |
| 🔄 | `RESET` | Reinicia el sistema |

---

## Flujo de Trabajo Completo

### Fase 1 — Captura de Dataset

1. Ir a tab **⚙️ Configuración** → conectar cámara
2. Ir a tab **📸 Captura Dataset**
3. Seleccionar carpeta de salida
4. Definir lote (ej: `lote_01`) y clase (ej: `botella_con_tapa`)
5. Cantidad: cuántas fotos por ráfaga (recomendado 50–100)
6. Intervalo: cada cuántos ms toma una foto (500 ms = 2 fotos/seg)
7. Pulsar **TOMAR RÁFAGA**
8. Repetir para cada clase

Estructura de carpetas generada automáticamente:

```
dataset/
  lote_01/
    botella_con_tapa/   → 50 imágenes
    botella_sin_tapa/   → 50 imágenes
    lata/               → 50 imágenes
    ninguno/            → 50 imágenes
```

### Fase 2 — Etiquetado en Roboflow

1. Comprimir la carpeta `dataset/` en un `.zip`
2. Subir a [roboflow.com](https://roboflow.com)
3. Crear proyecto tipo **Object Detection**
4. Importar imágenes con estructura de carpetas → auto-asigna clases
5. Etiquetar bounding boxes manualmente
6. Exportar en formato **YOLOv11** → descarga `dataset.zip`

### Fase 3 — Entrenamiento

```bash
# Con Google Colab (GPU T4/A100) o localmente (GPU recomendado)
yolo detect train data=dataset.yaml model=yolo11n.pt epochs=100 imgsz=640
```

> El modelo `yolo11n.pt` (nano) es ideal para hardware limitado. Usar `yolo11s.pt` o `yolo11m.pt` si se dispone de GPU dedicada.

### Fase 4 — Detección en Producción

1. Tab **⚙️ Configuración** → conectar cámara + puerto ESP32
2. Tab **🧠 Detección** → "Cargar modelo" → seleccionar `.pt` entrenado
3. Ajustar umbral de **confianza** e **IOU** en los sliders
4. El sistema envía comandos `SORT:N` al ESP32 automáticamente según la detección
5. Control manual de la banda disponible en el panel lateral

---

## Arquitectura del Software

```
CameraThread (QThread)
    │  frame_ready signal (BGR np.ndarray, ~30 fps)
    ├──→ CaptureTab.receive_frame()     (guarda si está en ráfaga)
    └──→ DetectionTab.receive_frame() → YOLOWorker.submit_frame()

YOLOWorker (QThread)
    │  result_ready signal (frame anotado + lista detecciones)
    └──→ DetectionTab._on_result()      (muestra + log + serial auto)

SerialManager (QObject)
    ├── SerialReader (QThread interno — lectura no bloqueante)
    └── Métodos: belt_start/stop, gate_open/close, sort(n)

MainWindow
    ├── distribuye frames entre tabs
    ├── gestiona status bar global
    └── cierre limpio de todos los hilos
```

---

## Clases del Dataset

| ID | Clase | Descripción |
|---|---|---|
| 0 | `botella_con_tapa` | Botella PET con tapa — más común en contenedores |
| 1 | `botella_sin_tapa` | Botella PET sin tapa — frecuente en basura |
| 2 | `lata_coca` | Lata Coca-Cola — color rojo, reflectante |
| 3 | `lata_pepsi` | Lata Pepsi — azul/rojo, textura similar |
| 4 | `lata_generica` | Lata sin marca clara visible |
| 5 | `ninguno` | Sin objeto relevante en cuadro |

> Puedes agregar clases nuevas directamente desde la UI sin modificar el código.

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/LMHDPRO/intelligent-recycling-system-YOLO.git
cd intelligent-recycling-system-YOLO

# 2. Crear entorno virtual (recomendado)
python -m venv .venv
.venv\Scripts\activate         # Windows
# source .venv/bin/activate    # Linux / macOS

# 3. Instalar dependencias base
pip install -r requirements.txt

# 4. Instalar Ultralytics YOLO (cuando tengas el modelo)
pip install ultralytics

# 5. Ejecutar
python main.py
```

### Dependencias

| Paquete | Versión mín. | Uso |
|---|---|---|
| `PySide6` | ≥ 6.6.0 | UI Qt — ventana, tabs, widgets, señales |
| `opencv-python` | ≥ 4.9.0 | Captura de cámara y procesamiento de frames |
| `pyserial` | ≥ 3.5 | Comunicación Serial con ESP32 por UART |
| `ultralytics` | ≥ 8.1.0 | YOLOv11 — inferencia sobre frames de cámara |
| `numpy` | stdlib/pip | Manipulación de arrays de imagen (BGR) |

---

## Protocolo Serial — Ejemplo Firmware ESP32

```cpp
void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if      (cmd == "BELT:START")          beltStart();
    else if (cmd == "BELT:STOP")           beltStop();
    else if (cmd.startsWith("BELT:SPEED:")) {
      int v = cmd.substring(11).toInt();   // 0–100
      setBeltSpeed(v);
    }
    else if (cmd == "GATE:OPEN")           gateOpen();
    else if (cmd == "GATE:CLOSE")          gateClose();
    else if (cmd == "SORT:0")              setSort(DISCARD);
    else if (cmd == "SORT:1")              setSort(BOTTLE);
    else if (cmd == "SORT:2")              setSort(CAN);
    else if (cmd == "E_STOP")             emergencyStop();
    else if (cmd == "RESET")              systemReset();

    Serial.println("OK");   // confirmación visible en el log de la UI
  }
}
```

> Todos los comandos están terminados en `\n`. La respuesta `OK` aparece en el log de la tab de Detección.

---

## Tips para el Dataset

- **Variedad**: capturar distintos ángulos, iluminaciones y fondos
- **Mínimo recomendado**: 200 imágenes por clase
- **Evitar**: duplicados de la misma posición o frame estático
- **Intervalo óptimo**: 500–1000 ms entre fotos para diversidad
- **Contexto realista**: capturar en el mismo ambiente de producción donde operará la máquina
- **Balance**: mantener proporciones similares entre clases para evitar sesgo

---

## Estructura del Proyecto

```
intelligent-recycling-system-YOLO/
 ├── main.py                 ← Punto de entrada — QApplication + MainWindow
 ├── requirements.txt        ← Dependencias base (sin ultralytics)
 ├── core/
 │    ├── camera_thread.py   ← Captura de frames a ~30fps (QThread)
 │    ├── yolo_worker.py     ← Inferencia YOLO en hilo separado (QThread)
 │    └── serial_manager.py  ← Comunicación ESP32: SerialReader + comandos
 └── ui/
      ├── main_window.py     ← Ventana principal — distribución de frames y status bar
      ├── capture_tab.py     ← Tab de captura de dataset con ráfaga automática
      ├── detection_tab.py   ← Tab de detección: video anotado + log + control serial
      ├── config_tab.py      ← Tab de configuración: cámara y puerto serial
      └── widgets.py         ← Widgets compartidos entre tabs
```

---

## Equipo

*Proyecto desarrollado en la* **Universidad Anáhuac Mayab** *— Mérida, Yucatán*

|  | Nombre | |
|---|---|---|
| 🧑‍💻 | **José Pardiñaz** | [LinkedIn](https://www.linkedin.com/in/josepardinaz/) |
| 🧑‍💻 | **William Monje** | [LinkedIn](https://www.linkedin.com/in/william-alejandro-monje-cano-1140a6242/) |
| 🧑‍💻 | **Jesus Moreno** | [LinkedIn](https://www.linkedin.com/in/jesus-montero5420/) |

[![Anáhuac Mayab](https://img.shields.io/badge/Universidad_Anáhuac_Mayab-Mérida,_MX-D4111A?style=for-the-badge)](https://merida.anahuac.mx/)

---

## Créditos de Librerías

- [Ultralytics YOLOv11](https://github.com/ultralytics/ultralytics) — Ultralytics Inc.
- [PySide6](https://doc.qt.io/qtforpython/) — The Qt Company
- [OpenCV](https://opencv.org/) — OpenCV Community
- [PySerial](https://github.com/pyserial/pyserial) — Chris Liechti

---

## Licencia

**MIT License** — Úsalo, modifícalo y distribúyelo libremente.

---

*RecyclerVision · YOLOv11 Recycling Classifier · Made with ☕ in Mérida, MX*
