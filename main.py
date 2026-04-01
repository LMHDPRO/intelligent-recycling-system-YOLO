"""
RecyclerVision — Sistema de Visión por Computadora para Clasificación de Residuos
==================================================================================
Universidad Anáhuac Mayab · Mérida, Yucatán

Estructura del proyecto:
  recycler_vision_Parcial2/
  ├── main.py                   ← Punto de entrada
  ├── requirements.txt
  ├── pipeline_config.json      ← Config unificada (captura + pipeline + máquina)
  ├── core/
  │   ├── camera_thread.py      ← Captura de frames ~30fps (QThread)
  │   ├── config_loader.py      ← Lectura/escritura de pipeline_config.json
  │   ├── pipeline_worker.py    ← Pipeline de N modelos YOLO en cascada (QThread)
  │   ├── serial_manager.py     ← Comunicación ESP32 UART (QThread interno)
  │   └── yolo_worker.py        ← Worker YOLO simple (legado / referencia)
  └── ui/
      ├── main_window.py        ← Ventana principal + distribución de frames
      ├── capture_tab.py        ← Captura de dataset con ráfaga automática
      ├── detection_tab.py      ← Detección en cascada + control de máquina
      ├── config_tab.py         ← Cámara y puerto serial
      ├── pipeline_panel.py     ← Diálogo flotante de configuración del pipeline
      └── widgets.py            ← VideoLabel, StatusLED

Protocolo Serial (ESP32 @ 115200 baud, comandos terminados en '\\n'):
  BELT:START        → Arranca banda transportadora (NEMA17 continuo)
  BELT:STOP         → Para banda
  BELT:SPEED:800    → Velocidad en steps/seg
  SERVO1:OPEN/CLOSE → Servo 1 (compuerta carril A)
  SERVO2:OPEN/CLOSE → Servo 2 (compuerta carril B)
  SORT:0            → Sorting a posición 0 (descarte)
  SORT:1            → Sorting a posición 1 (botella)
  SORT:2            → Sorting a posición 2 (lata)
  SORT_POS:1:400    → Calibra pasos para clase 1
  HOME              → Sorting a home
  STATUS            → Solicita estado completo del ESP32
  E_STOP            → Paro de emergencia inmediato
  RESET             → Limpia estado de emergencia

Eventos ESP32 → PC:
  RECYCLER_VISION:READY   → ESP32 listo
  US:15:8                 → Distancias US1=15cm  US2=8cm (cada ~100ms)
  EVENT:OBJ_ENTRY         → US1 detectó objeto → banda arrancó
  EVENT:OBJ_AT_CAM        → US2 detectó objeto → banda paró, listo para detección
  EVENT:TIMEOUT           → Sin SORT en 6s → banda reinició
  SORT:DONE:n             → Clasificación completada
  HOME:DONE               → Sorting en posición home
"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore    import Qt
from ui.main_window    import MainWindow


def main():
    # Soporte HiDPI (pantallas 4K / Retina)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("RecyclerVision")
    app.setApplicationVersion("2.1.0")
    app.setOrganizationName("Anáhuac Mayab")
    app.setStyle("Fusion")   # base consistente en Windows / Linux / Mac

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()