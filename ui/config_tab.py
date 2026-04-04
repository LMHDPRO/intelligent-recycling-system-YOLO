"""
Tab de Configuración:
  • Cámara: nombres reales del dispositivo, resolución, conectar/desconectar
  • Conexión ESP32: selector USB Serial / WiFi TCP + log + comandos manuales
  • Tabla de Precios: Visualización de las reglas de valoración desde el JSON
"""
import os
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QComboBox, QPushButton, QLineEdit,
    QTextEdit, QFormLayout, QFrame, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QRadioButton, QButtonGroup, QStackedWidget
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui  import QFont, QColor, QIntValidator

from core.camera_thread      import CameraThread, get_camera_names
from core.serial_manager     import SerialManager
from core.connection_manager import ConnectionManager
from ui.widgets              import StatusLED


# ── Hilo para detección de cámaras (no bloquea UI) ────────────────────────
class _CamScanThread(QThread):
    done = Signal(list)   # [(int, str)]

    def run(self):
        self.done.emit(get_camera_names())


# ─────────────────────────────────────────────────────────────────────────
class ConfigTab(QWidget):
    camera_connected    = Signal(int)
    camera_disconnected = Signal()

    def __init__(self, camera: CameraThread, conn: ConnectionManager):
        super().__init__()
        self._cam         = camera
        self._conn        = conn
        self._cam_running = False
        self._scan_thread: _CamScanThread | None = None
        self._build_ui()
        self._connect_signals()
        self._scan_cameras()   # escanear al inicio sin bloquear

    # ──────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 20, 20, 20)

        left_col = QVBoxLayout()
        left_col.addWidget(self._build_camera_group())
        left_col.addWidget(self._build_connection_group())
        left_col.addStretch()

        right_col = QVBoxLayout()
        right_col.addWidget(self._build_pricing_group())

        root.addLayout(left_col, stretch=1)
        root.addLayout(right_col, stretch=1)

    # ── Grupo Cámara ──────────────────────────────────────────────────────
    def _build_camera_group(self) -> QGroupBox:
        g = QGroupBox("📷  Cámara")
        g.setStyleSheet(GROUP_STYLE)
        lay = QFormLayout(g)
        lay.setSpacing(10)
        lay.setLabelAlignment(Qt.AlignRight)

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

        self.combo_res = QComboBox()
        self.combo_res.addItems(["1280×720  (HD)", "640×480  (VGA)", "1920×1080  (FHD)"])
        lay.addRow("Resolución:", self.combo_res)

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

    # ── Grupo Conexión ESP32 (Serial USB / WiFi TCP) ──────────────────────
    def _build_connection_group(self) -> QGroupBox:
        g = QGroupBox("🔌  ESP32  —  Conexión")
        g.setStyleSheet(GROUP_STYLE)

        root = QVBoxLayout(g)
        root.setSpacing(10)
        root.setContentsMargins(12, 14, 12, 12)

        # ── Selector de modo ──────────────────────────────────────────────
        self.radio_serial = QRadioButton("🔌  USB Serial")
        self.radio_wifi   = QRadioButton("📡  WiFi TCP")
        self.radio_serial.setChecked(True)
        self.radio_serial.setStyleSheet(RADIO_CSS)
        self.radio_wifi.setStyleSheet(RADIO_CSS)

        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self.radio_serial, 0)
        self._mode_group.addButton(self.radio_wifi,   1)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(16)
        mode_row.addWidget(self.radio_serial)
        mode_row.addWidget(self.radio_wifi)
        mode_row.addStretch()
        root.addLayout(mode_row)

        # ── Separador fino ────────────────────────────────────────────────
        sep0 = QFrame(); sep0.setFrameShape(QFrame.HLine)
        sep0.setStyleSheet("color:#21262d;"); root.addWidget(sep0)

        # ── Stack: Página 0 = Serial, Página 1 = WiFi ─────────────────────
        self.stack_conn = QStackedWidget()
        self.stack_conn.addWidget(self._build_serial_page())
        self.stack_conn.addWidget(self._build_wifi_page())
        root.addWidget(self.stack_conn)

        # ── LED + estado (compartido) ─────────────────────────────────────
        sep1 = QFrame(); sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet("color:#21262d;"); root.addWidget(sep1)

        self.led_conn          = StatusLED(16)
        self.label_conn_status = QLabel("Desconectado")
        self.label_conn_status.setStyleSheet("color:#555; font-size:11px;")

        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Estado:"))
        status_row.addWidget(self.led_conn)
        status_row.addWidget(self.label_conn_status, stretch=1)
        root.addLayout(status_row)

        # ── Separador ─────────────────────────────────────────────────────
        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color:#21262d;"); root.addWidget(sep2)

        # ── Comando manual (compartido) ───────────────────────────────────
        self.input_cmd = QLineEdit()
        self.input_cmd.setPlaceholderText("Ej: BELT:START  o  STATUS")
        self.btn_send  = QPushButton("Enviar")
        self.btn_send.setEnabled(False)

        cmd_form = QFormLayout()
        cmd_form.setSpacing(8)
        cmd_form.setLabelAlignment(Qt.AlignRight)
        row_cmd = QHBoxLayout()
        row_cmd.addWidget(self.input_cmd)
        row_cmd.addWidget(self.btn_send)
        cmd_form.addRow("Comando:", row_cmd)
        root.addLayout(cmd_form)

        # ── Log (compartido) ──────────────────────────────────────────────
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
        root.addWidget(self.serial_log)

        self.btn_clear_log = QPushButton("Limpiar log")
        self.btn_clear_log.setFixedHeight(22)
        self.btn_clear_log.clicked.connect(self.serial_log.clear)
        root.addWidget(self.btn_clear_log, alignment=Qt.AlignRight)

        return g

    def _build_serial_page(self) -> QWidget:
        """Página 0 del stack: configuración USB Serial."""
        page = QWidget()
        lay  = QFormLayout(page)
        lay.setSpacing(8)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setLabelAlignment(Qt.AlignRight)

        # Puerto COM
        self.combo_port = QComboBox()
        self.combo_port.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.btn_port_refresh = QPushButton("↺")
        self.btn_port_refresh.setFixedSize(30, 28)
        self.btn_port_refresh.setToolTip("Refrescar puertos")

        row_port = QHBoxLayout()
        row_port.addWidget(self.combo_port)
        row_port.addWidget(self.btn_port_refresh)
        lay.addRow("Puerto COM:", row_port)

        # Baudrate
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(SerialManager.BAUDRATES)
        self.combo_baud.setCurrentText("115200")
        lay.addRow("Baudrate:", self.combo_baud)

        # Botones
        self.btn_ser_connect    = QPushButton("▶  Conectar USB")
        self.btn_ser_connect.setStyleSheet(BTN_GREEN)
        self.btn_ser_disconnect = QPushButton("■  Desconectar")
        self.btn_ser_disconnect.setEnabled(False)

        row_ser = QHBoxLayout()
        row_ser.addWidget(self.btn_ser_connect)
        row_ser.addWidget(self.btn_ser_disconnect)
        lay.addRow("", row_ser)

        return page

    def _build_wifi_page(self) -> QWidget:
        """Página 1 del stack: configuración WiFi TCP."""
        page = QWidget()
        lay  = QFormLayout(page)
        lay.setSpacing(8)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setLabelAlignment(Qt.AlignRight)

        # IP
        self.input_wifi_ip = QLineEdit()
        self.input_wifi_ip.setPlaceholderText("192.168.x.x")
        self.input_wifi_ip.setStyleSheet(INPUT_CSS)
        lay.addRow("IP ESP32:", self.input_wifi_ip)

        # Puerto TCP
        self.input_wifi_port = QLineEdit("8888")
        self.input_wifi_port.setValidator(QIntValidator(1, 65535))
        self.input_wifi_port.setFixedWidth(70)
        self.input_wifi_port.setStyleSheet(INPUT_CSS)
        lay.addRow("Puerto TCP:", self.input_wifi_port)

        # Hint
        hint = QLabel("💡 Ver IP en el Monitor Serial del ESP32 (STATUS)")
        hint.setStyleSheet("color:#8b949e; font-size:10px; font-style:italic;")
        hint.setWordWrap(True)
        lay.addRow("", hint)

        # Botones
        self.btn_wifi_connect    = QPushButton("▶  Conectar WiFi")
        self.btn_wifi_connect.setStyleSheet(BTN_BLUE)
        self.btn_wifi_disconnect = QPushButton("■  Desconectar")
        self.btn_wifi_disconnect.setEnabled(False)

        row_wifi = QHBoxLayout()
        row_wifi.addWidget(self.btn_wifi_connect)
        row_wifi.addWidget(self.btn_wifi_disconnect)
        lay.addRow("", row_wifi)

        return page

    # ── Grupo Tabla de Precios ────────────────────────────────────────────
    def _build_pricing_group(self) -> QGroupBox:
        g = QGroupBox("💰  Tabla de Clases y Valorización (Solo lectura)")
        g.setStyleSheet(GROUP_STYLE)
        lay = QVBoxLayout(g)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Tipo", "Marca", "Tamaño", "Estado", "Precio ($)"])
        self.table.verticalHeader().setVisible(False)
        self.table.setFrameShape(QFrame.NoFrame)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0d1117;
                alternate-background-color: #161b22;
                color: #c9d1d9;
                gridline-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 6px;
                outline: 0;
            }
            QHeaderView::section {
                background-color: #21262d;
                color: #c9d1d9;
                font-weight: bold;
                border: none;
                border-bottom: 2px solid #30363d;
                border-right: 1px solid #21262d;
                padding: 6px;
            }
            QHeaderView::section:last { border-right: none; }
            QTableWidget::item { padding: 4px 8px; border-bottom: 1px solid #161b22; }
        """)

        base_dir    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "pipeline_config.json")
        rules = []
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg   = json.load(f)
                rules = cfg.get("valuation", {}).get("rules", [])
        except Exception:
            pass

        self.table.setRowCount(len(rules))
        for row, rule in enumerate(rules):
            def _mk(text):
                it = QTableWidgetItem(text)
                if text == "*":
                    it.setForeground(QColor("#6e7681"))
                    it.setTextAlignment(Qt.AlignCenter)
                else:
                    it.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                return it

            self.table.setItem(row, 0, _mk(rule.get("type",      "*")))
            self.table.setItem(row, 1, _mk(rule.get("brand",     "*")))
            self.table.setItem(row, 2, _mk(rule.get("size",      "*")))
            self.table.setItem(row, 3, _mk(rule.get("condition", "*")))

            price_val  = rule.get("price_mxn", 0.0)
            price_item = QTableWidgetItem(f"${price_val:.2f}")
            price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            price_item.setForeground(QColor("#3fb950" if price_val > 0 else "#f85149"))
            font = QFont(); font.setBold(True); price_item.setFont(font)
            self.table.setItem(row, 4, price_item)

        lay.addWidget(self.table)
        info = QLabel(
            "<i>Para modificar precios o clases, edita <b>pipeline_config.json</b> y reinicia la app.</i>"
        )
        info.setStyleSheet("color:#8b949e; font-size:11px;")
        lay.addWidget(info)
        return g

    # ──────────────────────────────────────────────────────────────────────
    def _connect_signals(self):
        # ── Cámara ────────────────────────────────────────────────────────
        self.btn_cam_refresh.clicked.connect(self._scan_cameras)
        self.btn_cam_connect.clicked.connect(self._connect_camera)
        self.btn_cam_disconnect.clicked.connect(self._disconnect_camera)
        self._cam.started_ok.connect(self._on_cam_started)
        self._cam.error.connect(self._on_cam_error)

        # ── Modo ──────────────────────────────────────────────────────────
        self.radio_serial.toggled.connect(self._on_mode_toggled)

        # ── Serial ────────────────────────────────────────────────────────
        self.btn_port_refresh.clicked.connect(self._refresh_ports)
        self.btn_ser_connect.clicked.connect(self._connect_serial)
        self.btn_ser_disconnect.clicked.connect(self._disconnect_serial)

        # ── WiFi ──────────────────────────────────────────────────────────
        self.btn_wifi_connect.clicked.connect(self._connect_wifi)
        self.btn_wifi_disconnect.clicked.connect(self._disconnect_wifi)

        # ── Comando + log ─────────────────────────────────────────────────
        self.btn_send.clicked.connect(self._send_command)
        self.input_cmd.returnPressed.connect(self._send_command)

        # ── ConnectionManager (reenvía solo desde el manager activo) ──────
        self._conn.status_changed.connect(self._on_conn_status)
        self._conn.data_received.connect(self._on_conn_rx)
        self._conn.connected.connect(self._on_conn_connected)

        self._refresh_ports()

    # ── Escaneo de cámaras ────────────────────────────────────────────────
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

    # ── Modo Serial / WiFi ────────────────────────────────────────────────
    def _on_mode_toggled(self, serial_checked: bool):
        mode = ConnectionManager.MODE_SERIAL if serial_checked else ConnectionManager.MODE_WIFI
        self._conn.set_mode(mode)
        self.stack_conn.setCurrentIndex(0 if serial_checked else 1)
        self._log(f"[Modo] {'USB Serial' if serial_checked else 'WiFi TCP'}")

    # ── Serial ────────────────────────────────────────────────────────────
    def _refresh_ports(self):
        self.combo_port.clear()
        ports = SerialManager.list_ports()
        self.combo_port.addItems(ports if ports else ["(sin puertos)"])

    def _connect_serial(self):
        self._conn.serial.connect(
            self.combo_port.currentText(),
            int(self.combo_baud.currentText())
        )

    def _disconnect_serial(self):
        self._conn.serial.disconnect()

    # ── WiFi ──────────────────────────────────────────────────────────────
    def _connect_wifi(self):
        host = self.input_wifi_ip.text().strip()
        if not host:
            self._log("⚠️ Ingresa la IP del ESP32")
            return
        try:
            port = int(self.input_wifi_port.text().strip())
        except ValueError:
            port = 8888
        self._conn.wifi.connect(host, port)

    def _disconnect_wifi(self):
        self._conn.wifi.disconnect()

    # ── Comando + log ─────────────────────────────────────────────────────
    def _send_command(self):
        cmd = self.input_cmd.text().strip()
        if cmd:
            ok = self._conn.send(cmd)
            self._log(f"{'→' if ok else '✗'} {cmd}")
            self.input_cmd.clear()

    # ── Slots del ConnectionManager ───────────────────────────────────────
    def _on_conn_status(self, msg: str):
        self.label_conn_status.setText(msg)
        if "✅" in msg:
            color = "#00d4aa"
        elif "❌" in msg:
            color = "#ff4757"
        elif "⚠️" in msg:
            color = "#ffa500"
        elif "🔄" in msg:
            color = "#58a6ff"
        else:
            color = "#555"
        self.label_conn_status.setStyleSheet(f"color:{color}; font-size:11px;")
        self._log(f"[SYS] {msg}")

    def _on_conn_rx(self, data: str):
        self._log(f"← {data}")

    def _on_conn_connected(self, ok: bool):
        self.led_conn.set_ok() if ok else self.led_conn.set_idle()
        self.btn_send.setEnabled(ok)

        # Actualizar botones del modo activo
        if self._conn.mode == ConnectionManager.MODE_SERIAL:
            self.btn_ser_connect.setEnabled(not ok)
            self.btn_ser_disconnect.setEnabled(ok)
        else:
            self.btn_wifi_connect.setEnabled(not ok)
            self.btn_wifi_disconnect.setEnabled(ok)

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
QPushButton {
    background:#196c2e; color:#fff; border-radius:5px;
    font-weight:bold; padding:5px 10px;
}
QPushButton:hover    { background:#238636; }
QPushButton:disabled { background:#21262d; color:#484f58; }
"""
BTN_BLUE = """
QPushButton {
    background:#0d419d; color:#fff; border-radius:5px;
    font-weight:bold; padding:5px 10px;
}
QPushButton:hover    { background:#1158c7; }
QPushButton:disabled { background:#21262d; color:#484f58; }
"""
RADIO_CSS = """
QRadioButton {
    color:#c9d1d9; font-size:13px; font-weight:bold; spacing:6px;
}
QRadioButton::indicator {
    width:16px; height:16px;
    border-radius:8px; border:2px solid #30363d;
    background:#0d1117;
}
QRadioButton::indicator:checked  { background:#1158c7; border-color:#58a6ff; }
QRadioButton::indicator:hover    { border-color:#8b949e; }
"""
INPUT_CSS = """
QLineEdit {
    background:#161b22; color:#c9d1d9;
    border:1px solid #30363d; border-radius:4px;
    font-size:13px; padding:3px 8px;
}
QLineEdit:focus { border-color:#58a6ff; }
"""
