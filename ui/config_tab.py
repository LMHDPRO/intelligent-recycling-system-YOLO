"""
Tab de Configuración:
  • Cámara: nombres reales del dispositivo, resolución, conectar/desconectar
  • Serial: puerto COM, baudrate, test, log

Mejoras UI v2:
  • Nombres reales de cámara (DirectShow / PnP)
  • Indicadores LED animados
  • Layout más compacto y legible
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QComboBox, QPushButton, QLineEdit,
    QTextEdit, QFormLayout, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui  import QFont

from core.camera_thread  import CameraThread, get_camera_names
from core.serial_manager import SerialManager
from ui.widgets          import StatusLED


# ── Hilo para detección de cámaras (no bloquea UI) ────────────────────────
class _CamScanThread(QThread):
    done = Signal(list)   # [(int, str)]

    def run(self):
        self.done.emit(get_camera_names())


# ─────────────────────────────────────────────────────────────────────────
class ConfigTab(QWidget):
    camera_connected    = Signal(int)
    camera_disconnected = Signal()

    def __init__(self, camera: CameraThread, serial: SerialManager):
        super().__init__()
        self._cam         = camera
        self._serial      = serial
        self._cam_running = False
        self._scan_thread: _CamScanThread | None = None
        self._build_ui()
        self._connect_signals()
        self._scan_cameras()   # escanear al inicio sin bloquear

    # ──────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 20, 20, 20)
        root.addWidget(self._build_camera_group())
        root.addWidget(self._build_serial_group())
        root.addStretch()

    # ── Grupo Cámara ──────────────────────────────────────────────────────
    def _build_camera_group(self) -> QGroupBox:
        g = QGroupBox("📷  Cámara")
        g.setStyleSheet(GROUP_STYLE)
        lay = QFormLayout(g)
        lay.setSpacing(10)
        lay.setLabelAlignment(Qt.AlignRight)

        # Selector con nombre real
        self.combo_cam = QComboBox()
        self.combo_cam.setMinimumWidth(220)
        self.combo_cam.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.led_cam = StatusLED(16)

        self.btn_cam_refresh = QPushButton("↺")
        self.btn_cam_refresh.setFixedSize(30, 28)
        self.btn_cam_refresh.setToolTip("Buscar cámaras")

        self.label_scan = QLabel("Escaneando…")
        self.label_scan.setStyleSheet("color:#555; font-size:10px;")

        row_cam = QHBoxLayout()
        row_cam.addWidget(self.combo_cam)
        row_cam.addWidget(self.btn_cam_refresh)
        row_cam.addWidget(self.led_cam)
        lay.addRow("Dispositivo:", row_cam)
        lay.addRow("", self.label_scan)

        # Resolución
        self.combo_res = QComboBox()
        self.combo_res.addItems(["1280×720  (HD)", "640×480  (VGA)", "1920×1080  (FHD)"])
        lay.addRow("Resolución:", self.combo_res)

        # Botones
        self.btn_cam_connect    = QPushButton("▶  Conectar")
        self.btn_cam_connect.setStyleSheet(BTN_GREEN)
        self.btn_cam_disconnect = QPushButton("■  Desconectar")
        self.btn_cam_disconnect.setEnabled(False)
        self.label_cam_status   = QLabel("Sin cámara")
        self.label_cam_status.setStyleSheet("color:#555; font-size:11px;")

        row_btn = QHBoxLayout()
        row_btn.addWidget(self.btn_cam_connect)
        row_btn.addWidget(self.btn_cam_disconnect)
        lay.addRow("", row_btn)
        lay.addRow("Estado:", self.label_cam_status)
        return g

    # ── Grupo Serial ──────────────────────────────────────────────────────
    def _build_serial_group(self) -> QGroupBox:
        g = QGroupBox("🔌  ESP32  —  Serial")
        g.setStyleSheet(GROUP_STYLE)
        lay = QFormLayout(g)
        lay.setSpacing(10)
        lay.setLabelAlignment(Qt.AlignRight)

        self.combo_port = QComboBox()
        self.combo_port.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.btn_port_refresh = QPushButton("↺")
        self.btn_port_refresh.setFixedSize(30, 28)
        self.led_serial = StatusLED(16)

        row_port = QHBoxLayout()
        row_port.addWidget(self.combo_port)
        row_port.addWidget(self.btn_port_refresh)
        row_port.addWidget(self.led_serial)
        lay.addRow("Puerto COM:", row_port)

        self.combo_baud = QComboBox()
        self.combo_baud.addItems(SerialManager.BAUDRATES)
        self.combo_baud.setCurrentText("115200")
        lay.addRow("Baudrate:", self.combo_baud)

        self.btn_ser_connect    = QPushButton("▶  Conectar ESP32")
        self.btn_ser_connect.setStyleSheet(BTN_GREEN)
        self.btn_ser_disconnect = QPushButton("■  Desconectar")
        self.btn_ser_disconnect.setEnabled(False)

        row_ser = QHBoxLayout()
        row_ser.addWidget(self.btn_ser_connect)
        row_ser.addWidget(self.btn_ser_disconnect)
        lay.addRow("", row_ser)

        self.label_serial_status = QLabel("Desconectado")
        self.label_serial_status.setStyleSheet("color:#555; font-size:11px;")
        lay.addRow("Estado:", self.label_serial_status)

        # Separador
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#21262d;"); lay.addRow(sep)

        # Comando manual
        self.input_cmd = QLineEdit()
        self.input_cmd.setPlaceholderText("Ej: BELT:START  o  STATUS")
        self.btn_send  = QPushButton("Enviar")
        self.btn_send.setEnabled(False)
        row_cmd = QHBoxLayout()
        row_cmd.addWidget(self.input_cmd)
        row_cmd.addWidget(self.btn_send)
        lay.addRow("Comando:", row_cmd)

        # Log
        self.serial_log = QTextEdit()
        self.serial_log.setReadOnly(True)
        self.serial_log.setMaximumHeight(150)
        self.serial_log.setFont(QFont("Consolas", 10))
        self.serial_log.setStyleSheet("""
            QTextEdit {
                background:#0d1117; color:#00d4aa;
                border:1px solid #21262d; border-radius:4px;
            }
        """)
        lay.addRow("Log:", self.serial_log)

        self.btn_clear_log = QPushButton("Limpiar log")
        self.btn_clear_log.setFixedHeight(22)
        self.btn_clear_log.clicked.connect(self.serial_log.clear)
        lay.addRow("", self.btn_clear_log)
        return g

    # ──────────────────────────────────────────────────────────────────────
    def _connect_signals(self):
        self.btn_cam_refresh.clicked.connect(self._scan_cameras)
        self.btn_cam_connect.clicked.connect(self._connect_camera)
        self.btn_cam_disconnect.clicked.connect(self._disconnect_camera)
        self._cam.started_ok.connect(self._on_cam_started)
        self._cam.error.connect(self._on_cam_error)

        self.btn_port_refresh.clicked.connect(self._refresh_ports)
        self.btn_ser_connect.clicked.connect(self._connect_serial)
        self.btn_ser_disconnect.clicked.connect(self._disconnect_serial)
        self.btn_send.clicked.connect(self._send_command)
        self.input_cmd.returnPressed.connect(self._send_command)

        self._serial.status_changed.connect(self._on_serial_status)
        self._serial.data_received.connect(self._on_serial_rx)
        self._serial.connected.connect(self._on_serial_connected)

        self._refresh_ports()

    # ── Escaneo de cámaras (async) ────────────────────────────────────────
    def _scan_cameras(self):
        self.label_scan.setText("Escaneando dispositivos…")
        self.btn_cam_refresh.setEnabled(False)
        self.combo_cam.clear()

        self._scan_thread = _CamScanThread()
        self._scan_thread.done.connect(self._on_scan_done)
        self._scan_thread.start()

    def _on_scan_done(self, cameras: list):
        self.combo_cam.clear()
        if cameras:
            for idx, name in cameras:
                self.combo_cam.addItem(f"[{idx}]  {name}", idx)
            self.label_scan.setText(f"{len(cameras)} cámara(s) detectada(s)")
            self.label_scan.setStyleSheet("color:#00d4aa; font-size:10px;")
        else:
            self.combo_cam.addItem("Sin cámaras detectadas", -1)
            self.label_scan.setText("No se encontraron cámaras")
            self.label_scan.setStyleSheet("color:#ff4757; font-size:10px;")
        self.btn_cam_refresh.setEnabled(True)

    # ── Cámara ────────────────────────────────────────────────────────────
    def _connect_camera(self):
        idx = self.combo_cam.currentData()
        if idx is None or idx < 0:
            return
        res_text = self.combo_res.currentText().split()[0]
        w, h = map(int, res_text.replace("×", "x").split("x"))
        self._cam.stop()
        self._cam.set_camera(idx)
        self._cam.set_resolution(w, h)
        self._cam.start()
        self.label_cam_status.setText("Conectando…")
        self.label_cam_status.setStyleSheet("color:#ffa500; font-size:11px;")

    def _disconnect_camera(self):
        self._cam.stop()
        self.led_cam.set_idle()
        self.label_cam_status.setText("Desconectada")
        self.label_cam_status.setStyleSheet("color:#555; font-size:11px;")
        self.btn_cam_connect.setEnabled(True)
        self.btn_cam_disconnect.setEnabled(False)
        self.camera_disconnected.emit()

    def _on_cam_started(self, idx: int):
        self.led_cam.set_ok()
        name = self.combo_cam.currentText()
        self.label_cam_status.setText(f"✅  {name}")
        self.label_cam_status.setStyleSheet("color:#00d4aa; font-size:11px;")
        self.btn_cam_connect.setEnabled(False)
        self.btn_cam_disconnect.setEnabled(True)
        self.camera_connected.emit(idx)

    def _on_cam_error(self, msg: str):
        self.led_cam.set_error()
        self.label_cam_status.setText(f"❌  {msg}")
        self.label_cam_status.setStyleSheet("color:#ff4757; font-size:11px;")

    # ── Serial ────────────────────────────────────────────────────────────
    def _refresh_ports(self):
        self.combo_port.clear()
        ports = SerialManager.list_ports()
        self.combo_port.addItems(ports if ports else ["(sin puertos)"])

    def _connect_serial(self):
        self._serial.connect(
            self.combo_port.currentText(),
            int(self.combo_baud.currentText())
        )

    def _disconnect_serial(self):
        self._serial.disconnect()

    def _send_command(self):
        cmd = self.input_cmd.text().strip()
        if cmd:
            ok = self._serial.send(cmd)
            self._log(f"{'→' if ok else '✗'} {cmd}")
            self.input_cmd.clear()

    def _on_serial_status(self, msg: str):
        self.label_serial_status.setText(msg)
        color = "#00d4aa" if "✅" in msg else "#ff4757" if "❌" in msg else "#555"
        self.label_serial_status.setStyleSheet(f"color:{color}; font-size:11px;")
        self._log(f"[SYS] {msg}")

    def _on_serial_rx(self, data: str):
        self._log(f"← {data}")

    def _on_serial_connected(self, ok: bool):
        self.led_serial.set_ok() if ok else self.led_serial.set_error()
        self.btn_ser_connect.setEnabled(not ok)
        self.btn_ser_disconnect.setEnabled(ok)
        self.btn_send.setEnabled(ok)

    def _log(self, text: str):
        self.serial_log.append(text)
        self.serial_log.verticalScrollBar().setValue(
            self.serial_log.verticalScrollBar().maximum()
        )


# ─── Estilos ─────────────────────────────────────────────────────────────
GROUP_STYLE = """
QGroupBox {
    font-weight:bold; font-size:13px; color:#c9d1d9;
    border:1px solid #30363d; border-radius:8px;
    margin-top:10px; padding-top:8px;
}
QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 6px; }
"""
BTN_GREEN = """
QPushButton { background:#196c2e; color:#fff; border-radius:5px; font-weight:bold; padding:5px 10px; }
QPushButton:hover { background:#238636; }
QPushButton:disabled { background:#21262d; color:#484f58; }
"""
from PySide6.QtWidgets import QHBoxLayout