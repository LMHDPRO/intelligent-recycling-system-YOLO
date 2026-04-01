# ♻️ RecyclerVision

Sistema de visión por computadora para clasificación de residuos (botellas / latas).

---

## 🚀 Instalación rápida

```bash
# 1. Clonar / copiar el proyecto
cd recycler_vision

# 2. Crear entorno virtual (recomendado)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# 3. Instalar dependencias base
pip install -r requirements.txt

# 4. (Cuando tengas el modelo) instalar YOLO
pip install ultralytics

# 5. Ejecutar
python main.py
```

---

## 🗂️ Flujo de trabajo

### Fase 1 — Captura de dataset
1. Ir a tab **Configuración** → conectar cámara
2. Ir a tab **📸 Captura Dataset**
3. Seleccionar carpeta de salida
4. Definir lote (ej: `lote_01`) y clase (ej: `botella_con_tapa`)
5. Cantidad: cuántas fotos por ráfaga (recomendado 50–100)
6. Intervalo: cada cuántos ms toma una foto (500 ms = 2 fotos/seg)
7. Pulsar **TOMAR RÁFAGA**
8. Repetir para cada clase

Estructura generada:
```
dataset/
  lote_01/
    botella_con_tapa/  → 50 imágenes
    botella_sin_tapa/  → 50 imágenes
    lata/              → 50 imágenes
    ninguno/           → 50 imágenes
```

### Fase 2 — Etiquetado en Roboflow
1. Comprimir la carpeta `dataset/` en un `.zip`
2. Subir a [roboflow.com](https://roboflow.com)
3. Crear proyecto tipo **Object Detection**
4. Importar imágenes con estructura de carpetas → auto-asigna clases
5. Etiquetar bounding boxes
6. Exportar en formato **YOLOv11** → descarga `dataset.zip`

### Fase 3 — Entrenamiento
```bash
# Con Google Colab o localmente (GPU recomendado)
yolo detect train data=dataset.yaml model=yolo11n.pt epochs=100 imgsz=640
```

### Fase 4 — Detección
1. Tab **⚙️ Configuración** → conectar cámara + ESP32
2. Tab **🧠 Detección** → "Cargar modelo" → seleccionar `.pt` entrenado
3. Ajustar umbrales de confianza e IOU
4. Controlar máquina desde el panel

---

## 🔌 Protocolo Serial ESP32

El sistema envía comandos por UART terminados en `\n`:

| Comando         | Función                    |
|----------------|----------------------------|
| `BELT:START`   | Arranca banda              |
| `BELT:STOP`    | Para banda                 |
| `BELT:SPEED:80`| Velocidad 0–100            |
| `GATE:OPEN`    | Abre actuador lineal       |
| `GATE:CLOSE`   | Cierra actuador lineal     |
| `SORT:0`       | Carril descarte / ninguno  |
| `SORT:1`       | Carril botella             |
| `SORT:2`       | Carril lata                |
| `E_STOP`       | Paro de emergencia         |
| `RESET`        | Reset sistema              |

### Ejemplo Arduino/ESP32
```cpp
void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if      (cmd == "BELT:START")  beltStart();
    else if (cmd == "BELT:STOP")   beltStop();
    else if (cmd.startsWith("BELT:SPEED:")) {
      int v = cmd.substring(11).toInt();
      setBeltSpeed(v);
    }
    else if (cmd == "GATE:OPEN")   gateOpen();
    else if (cmd == "GATE:CLOSE")  gateClose();
    else if (cmd == "SORT:0")      setSort(0);
    else if (cmd == "SORT:1")      setSort(1);
    else if (cmd == "SORT:2")      setSort(2);
    else if (cmd == "E_STOP")      emergencyStop();

    Serial.println("OK");   // respuesta que aparece en el log
  }
}
```

---

## 🏗️ Arquitectura del software

```
CameraThread (QThread)
    │ frame_ready signal (BGR np.ndarray, ~30fps)
    ├──→ CaptureTab.receive_frame()   (guarda si está en ráfaga)
    └──→ DetectionTab.receive_frame() → YOLOWorker.submit_frame()

YOLOWorker (QThread)
    │ result_ready signal (frame anotado + lista detecciones)
    └──→ DetectionTab._on_result()    (muestra + log + serial auto)

SerialManager (QObject)
    ├── SerialReader (QThread interno — lectura no bloqueante)
    └── Métodos: belt_start/stop, gate_open/close, sort(n)

MainWindow
    ├── distribuye frames entre tabs
    ├── gestiona status bar global
    └── cierre limpio de todos los hilos
```

---

## 📋 Clases recomendadas para tu dataset

| ID | Clase                | Descripción                       |
|----|---------------------|-----------------------------------|
| 0  | `botella_con_tapa`  | Botella PET con tapa              |
| 1  | `botella_sin_tapa`  | Botella PET sin tapa              |
| 2  | `lata_coca`         | Lata Coca-Cola                    |
| 3  | `lata_pepsi`        | Lata Pepsi                        |
| 4  | `lata_generica`     | Lata sin marca clara              |
| 5  | `ninguno`           | Sin objeto relevante              |

> Puedes agregar cualquier clase nueva directamente desde la UI (campo editable).

---

## 💡 Tips para el dataset

- **Variedad**: diferentes ángulos, iluminación, fondos
- **Mínimo recomendado**: 200 imágenes por clase
- **Evitar**: imágenes duplicadas de la misma posición
- **Intervalo ráfaga**: 500–1000 ms para evitar duplicados
- **Fondo**: usa el mismo contexto que la máquina real

---

## 📦 Dependencias

| Paquete          | Versión mín. | Uso                    |
|-----------------|-------------|------------------------|
| PySide6          | 6.6.0       | UI Qt                  |
| opencv-python    | 4.9.0       | Captura + procesamiento|
| pyserial         | 3.5         | Comunicación ESP32     |
| ultralytics      | 8.1.0       | YOLOv11 (opcional)     |
