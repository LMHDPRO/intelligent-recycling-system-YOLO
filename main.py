"""
RecyclerVision — Sistema de Visión por Computadora para Clasificación de Residuos
=================================================================================
Autor: Tu nombre
Proyecto: Clasificador Botella / Lata / Ninguno con YOLOv11

Estructura del proyecto:
  recycler_vision/
  ├── main.py               ← Punto de entrada
  ├── requirements.txt
  ├── core/
  │   ├── camera_thread.py  ← Captura de frames (QThread)
  │   ├── yolo_worker.py    ← Inferencia YOLO (QThread)
  │   └── serial_manager.py ← Comunicación ESP32 (Serial)
  └── ui/
      ├── main_window.py    ← Ventana principal
      ├── capture_tab.py    ← Tab de captura de dataset
      ├── detection_tab.py  ← Tab de detección con modelo
      ├── config_tab.py     ← Tab de configuración (cámara + serial)
      └── widgets.py        ← Widgets compartidos

Protocolo Serial (ESP32):
  BELT:START      → Arranca banda
  BELT:STOP       → Para banda
  BELT:SPEED:80   → Velocidad 0-100
  GATE:OPEN       → Abre actuador lineal
  GATE:CLOSE      → Cierra actuador lineal
  SORT:0          → Carril descarte
  SORT:1          → Carril botella
  SORT:2          → Carril lata
  E_STOP          → Paro de emergencia
  RESET           → Reset sistema
"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore    import Qt
from ui.main_window    import MainWindow


def main():
    # Soporte HiDPI
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("RecyclerVision")
    app.setApplicationVersion("1.0.0")
    app.setStyle("Fusion")   # base consistente en Windows/Linux/Mac

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
