"""
MainWindow — ventana principal.
  • Gestiona CameraThread (único, compartido entre tabs)
  • Gestiona YOLOWorker  (único, compartido)
  • Gestiona SerialManager (único, compartido)
  • Distribuye frames a CaptureTab y DetectionTab
  • Status bar unificado
"""
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QLabel, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui  import QIcon, QFont

from core.camera_thread  import CameraThread
from core.yolo_worker    import YOLOWorker
from core.serial_manager import SerialManager

from ui.capture_tab   import CaptureTab
from ui.detection_tab import DetectionTab
from ui.config_tab    import ConfigTab


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("♻️  RecyclerVision  —  Sistema de Clasificación")
        self.setMinimumSize(1100, 720)

        # ── Componentes core ──────────────────────────────────
        self._camera = CameraThread()
        self._yolo   = YOLOWorker()
        self._serial = SerialManager()

        # ── Tabs ──────────────────────────────────────────────
        self._tab_capture   = CaptureTab()
        self._tab_detection = DetectionTab(self._yolo, self._serial)
        self._tab_config    = ConfigTab(self._camera, self._serial)

        # ── TabWidget ─────────────────────────────────────────
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._tab_capture,   "📸  Captura Dataset")
        tabs.addTab(self._tab_detection, "🧠  Detección")
        tabs.addTab(self._tab_config,    "⚙️  Configuración")
        tabs.setStyleSheet(TAB_STYLE)
        self.setCentralWidget(tabs)

        # ── Status bar ────────────────────────────────────────
        self._status_cam    = QLabel("📷 Sin cámara")
        self._status_serial = QLabel("🔌 Sin serial")
        self._status_model  = QLabel("🧠 Sin modelo")

        for lbl in (self._status_cam, self._status_serial, self._status_model):
            lbl.setStyleSheet("color:#8b949e; padding: 0 8px;")

        sb = QStatusBar()
        sb.addPermanentWidget(self._status_cam)
        sb.addPermanentWidget(_separator())
        sb.addPermanentWidget(self._status_serial)
        sb.addPermanentWidget(_separator())
        sb.addPermanentWidget(self._status_model)
        self.setStatusBar(sb)

        # ── Conexiones entre componentes ──────────────────────
        self._wire_signals()
        self._apply_theme()

    # ──────────────────────────────────────────────────────────
    def _wire_signals(self):
        # Camera → tabs
        self._camera.frame_ready.connect(self._tab_capture.receive_frame)
        self._camera.frame_ready.connect(self._tab_detection.receive_frame)

        # Config → tabs (eventos de conexión)
        self._tab_config.camera_connected.connect(self._tab_capture.on_camera_connected)
        self._tab_config.camera_connected.connect(self._tab_detection.on_camera_connected)
        self._tab_config.camera_connected.connect(
            lambda idx: self._status_cam.setText(f"📷 Cámara {idx} ✅"))

        self._tab_config.camera_disconnected.connect(self._tab_capture.on_camera_disconnected)
        self._tab_config.camera_disconnected.connect(self._tab_detection.on_camera_disconnected)
        self._tab_config.camera_disconnected.connect(
            lambda: self._status_cam.setText("📷 Sin cámara"))

        # Serial status → status bar
        self._serial.status_changed.connect(
            lambda msg: self._status_serial.setText(f"🔌 {msg}"))

        # YOLO model → status bar
        self._yolo.model_loaded.connect(
            lambda ok, msg: self._status_model.setText(f"🧠 {msg}"))

        # Tab messages → status bar
        self._tab_capture.status_message.connect(self.statusBar().showMessage)
        self._tab_detection.status_message.connect(self.statusBar().showMessage)

    # ──────────────────────────────────────────────────────────
    def _apply_theme(self):
        self.setStyleSheet(APP_THEME)

    def closeEvent(self, event):
        """Cierre limpio: detener todos los hilos."""
        self._yolo.stop()
        self._camera.stop()
        self._serial.disconnect()
        event.accept()


# ─── Utilidades ──────────────────────────────────────────────
def _separator() -> QLabel:
    sep = QLabel("|")
    sep.setStyleSheet("color:#30363d;")
    return sep


# ─── Tema global (GitHub Dark inspired) ──────────────────────
APP_THEME = """
QMainWindow, QWidget {
    background-color: #0d1117;
    color: #c9d1d9;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #21262d;
    border-radius: 6px;
    background: #0d1117;
}
QTabBar::tab {
    background: #161b22;
    color: #8b949e;
    padding: 8px 18px;
    border: 1px solid #21262d;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    margin-right: 2px;
    font-size: 13px;
}
QTabBar::tab:selected {
    background: #0d1117;
    color: #c9d1d9;
    border-bottom-color: #0d1117;
}
QTabBar::tab:hover:!selected {
    background: #1c2128;
    color: #c9d1d9;
}
QGroupBox {
    border: 1px solid #30363d;
    border-radius: 6px;
    margin-top: 10px;
    color: #c9d1d9;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #c9d1d9;
}
QPushButton {
    background: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 5px;
    padding: 5px 12px;
}
QPushButton:hover   { background: #30363d; border-color: #8b949e; }
QPushButton:pressed { background: #161b22; }
QPushButton:disabled{ background: #161b22; color: #484f58; border-color: #21262d; }
QComboBox {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 3px 8px;
    color: #c9d1d9;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background: #161b22;
    border: 1px solid #30363d;
    color: #c9d1d9;
    selection-background-color: #1f6feb;
}
QLineEdit, QSpinBox {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 4px 8px;
    color: #c9d1d9;
}
QLineEdit:focus, QSpinBox:focus { border-color: #1f6feb; }
QSlider::groove:horizontal {
    height: 4px;
    background: #30363d;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #00d4aa;
    width: 14px; height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::sub-page:horizontal { background: #00d4aa; border-radius: 2px; }
QScrollBar:vertical {
    background: #161b22;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #30363d;
    border-radius: 4px;
}
QStatusBar { background: #161b22; border-top: 1px solid #21262d; }
QProgressBar {
    border: 1px solid #30363d;
    border-radius: 4px;
    text-align: center;
    background: #161b22;
}
QProgressBar::chunk { background: #00d4aa; border-radius: 3px; }
"""

TAB_STYLE = ""   # heredado del APP_THEME
