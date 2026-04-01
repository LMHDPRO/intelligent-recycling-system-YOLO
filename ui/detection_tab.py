"""
Tab de Detección v4.2 — bug fixes:
  • FIX: _stop_detection() ya NO envía E_STOP al ESP32 (era bug crítico)
  • FIX: galería usa rgb.data.tobytes() en lugar de rgb.data (estabilidad)
  • ADD: botón E-STOP visible en panel máquina (conectado a Space/Escape también)
  • Sin cambios de arquitectura respecto a v4.1
"""
import os
import cv2
import json
import numpy as np
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
    QLabel, QPushButton, QSlider, QFileDialog,
    QSizePolicy, QFormLayout, QTextEdit, QFrame,
    QCheckBox, QProgressBar, QRadioButton,
    QScrollArea, QSplitter
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui  import QFont, QShortcut, QKeySequence, QImage, QPixmap

from core.pipeline_worker import PipelineWorker, PipelineResult
from core.serial_manager  import SerialManager
from ui.widgets           import VideoLabel
from ui.pipeline_panel    import PipelineDialog


# ─── Barra ultrasónico ────────────────────────────────────────────────────
class _USBar(QWidget):
    MAX_CM = 100

    def __init__(self, title: str):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setSpacing(2)
        lay.setContentsMargins(0, 0, 0, 0)
        t = QLabel(title)
        t.setStyleSheet("color:#8b949e; font-size:10px;")
        t.setAlignment(Qt.AlignCenter)
        self._bar = QProgressBar()
        self._bar.setRange(0, self.MAX_CM)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(8)
        self._bar.setStyleSheet(_BAR.format(c="#00d4aa"))
        self._lbl = QLabel("—")
        self._lbl.setAlignment(Qt.AlignCenter)
        self._lbl.setStyleSheet(
            "color:#c9d1d9; font-size:11px; font-family:Consolas;")
        lay.addWidget(t)
        lay.addWidget(self._bar)
        lay.addWidget(self._lbl)

    def update(self, cm: int):
        self._bar.setValue(self.MAX_CM - min(cm, self.MAX_CM))
        self._lbl.setText("—" if cm >= 999 else f"{cm} cm")
        c = "#ff4757" if cm < 20 else "#ffa500" if cm < 40 else "#00d4aa"
        self._bar.setStyleSheet(_BAR.format(c=c))

_BAR = ("QProgressBar{{background:#161b22;border:1px solid #30363d;"
        "border-radius:3px;}} QProgressBar::chunk{{background:{c};border-radius:2px;}}")


# ─────────────────────────────────────────────────────────────────────────
class DetectionTab(QWidget):
    status_message = Signal(str)

    CLASS_SORT_MAP = {
        "botella":     1,
        "lata":        2,
        "desconocido": 0,
        "ninguno":     0,
        "—":           0,
    }

    def __init__(self, worker: PipelineWorker, serial: SerialManager):
        super().__init__()
        self._worker  = worker
        self._serial  = serial
        self._running = False
        self._auto    = False
        self._pending_auto_sort = False
        self._save_folder  = os.path.join(os.getcwd(), "detections")
        self._saved_count  = 0
        self._last_frame: np.ndarray | None = None
        self._pipeline_dlg = None
        self._build_ui()
        self._connect_signals()

    # ──────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(4)
        root.setContentsMargins(6, 6, 6, 6)

        # ── Barra superior: START + modo ──────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(8)

        self.btn_start = QPushButton("▶  START DETECCIÓN")
        self.btn_start.setFixedHeight(32)
        self.btn_start.setEnabled(False)
        self.btn_start.setStyleSheet(BTN_START_OFF)

        mode_box = QGroupBox("Modo")
        mode_box.setFixedWidth(160)
        mode_box.setStyleSheet("""
            QGroupBox { border:1px solid #30363d; border-radius:6px;
                        font-size:10px; color:#8b949e;
                        margin-top:6px; padding-top:2px; }
            QGroupBox::title { subcontrol-origin:margin; left:8px; }
        """)
        ml = QHBoxLayout(mode_box)
        ml.setContentsMargins(6, 2, 6, 2)
        ml.setSpacing(10)
        self.radio_auto   = QRadioButton("AUTO")
        self.radio_manual = QRadioButton("MANUAL")
        self.radio_manual.setChecked(True)
        for r in (self.radio_auto, self.radio_manual):
            r.setStyleSheet("color:#c9d1d9; font-weight:bold; font-size:12px;")
        ml.addWidget(self.radio_auto)
        ml.addWidget(self.radio_manual)

        top.addWidget(self.btn_start, stretch=1)
        top.addWidget(mode_box)
        root.addLayout(top, 0)

        # ── Splitter horizontal ───────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(5)
        splitter.setStyleSheet("""
            QSplitter::handle { background:#21262d; border-radius:2px; }
            QSplitter::handle:hover { background:#30363d; }
        """)

        # ── Zona izquierda: video + info + galería ────────────────────────
        left_w = QWidget()
        left_l = QVBoxLayout(left_w)
        left_l.setContentsMargins(0, 0, 0, 0)
        left_l.setSpacing(6)

        self.video = VideoLabel("📷  Conecta la cámara y carga los modelos")
        self.video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.label_info = QLabel("Estado: idle  |  Detecciones: —")
        self.label_info.setAlignment(Qt.AlignCenter)
        self.label_info.setFixedHeight(24)
        self.label_info.setStyleSheet(INFO_IDLE)

        left_l.addWidget(self.video, stretch=1)
        left_l.addWidget(self.label_info, stretch=0)
        left_l.addWidget(self._build_gallery(), stretch=0)

        # ── Zona derecha: controles con scroll ────────────────────────────
        right_w = QWidget()
        right_w.setMinimumWidth(320)
        right_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border:none; background:transparent; }
            QScrollBar:vertical { background:#0d1117; width:5px; border-radius:2px; }
            QScrollBar::handle:vertical { background:#30363d; border-radius:2px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
        """)

        inner = QWidget()
        inner_l = QVBoxLayout(inner)
        inner_l.setSpacing(8)
        inner_l.setContentsMargins(6, 4, 6, 6)

        inner_l.addWidget(self._grp_pipeline())
        inner_l.addWidget(self._grp_ultrasonics())
        inner_l.addWidget(self._grp_log())
        inner_l.addWidget(self._grp_save())
        inner_l.addWidget(self._grp_machine())
        inner_l.addStretch()

        scroll.setWidget(inner)

        rlay = QVBoxLayout(right_w)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.addWidget(scroll)

        splitter.addWidget(left_w)
        splitter.addWidget(right_w)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([600, 400])

        root.addWidget(splitter, 1)

    # ── Galería inferior ──────────────────────────────────────────────────
    def _build_gallery(self) -> QGroupBox:
        g = QGroupBox("🖼️  Últimas capturas analizadas")
        g.setStyleSheet(GS)
        g.setFixedHeight(110)
        lay = QHBoxLayout(g)
        lay.setSpacing(8)
        lay.setContentsMargins(8, 16, 8, 8)

        self.gallery_labels = []
        for _ in range(5):
            lbl = QLabel("Sin\ndatos")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                "background:#0d1117; border:1px dashed #30363d; "
                "border-radius:4px; color:#484f58; font-size:10px;")
            lbl.setScaledContents(True)
            self.gallery_labels.append(lbl)
            lay.addWidget(lbl)
        return g

    def _add_to_gallery(self, frame: np.ndarray):
        # Desplazar imágenes hacia la derecha
        for i in range(len(self.gallery_labels) - 1, 0, -1):
            pix = self.gallery_labels[i - 1].pixmap()
            if pix and not pix.isNull():
                self.gallery_labels[i].setPixmap(pix)

        # FIX: usar .tobytes() para estabilidad en todas las versiones de Python/Qt
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data.tobytes(), w, h, ch * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(img)
        self.gallery_labels[0].setStyleSheet(
            "background:#000; border:1px solid #58a6ff; border-radius:4px;")
        self.gallery_labels[0].setPixmap(pix)

    # ── Grupos del panel derecho ──────────────────────────────────────────
    def _grp_pipeline(self) -> QGroupBox:
        g = QGroupBox("🧠  Modelos YOLO en Cascada")
        g.setStyleSheet(GS)
        l = QVBoxLayout(g)
        l.setSpacing(6)
        l.setContentsMargins(10, 8, 10, 10)

        lbl = QLabel("Configura los modelos del pipeline y sus umbrales.")
        lbl.setStyleSheet("color:#8b949e; font-size:11px;")
        lbl.setWordWrap(True)

        self.btn_open_pipe = QPushButton("⚙️  Configurar Pipeline…")
        self.btn_open_pipe.setFixedHeight(30)
        self.btn_open_pipe.setStyleSheet(BTN_PRIMARY)

        l.addWidget(lbl)
        l.addWidget(self.btn_open_pipe)
        return g

    def _grp_ultrasonics(self) -> QGroupBox:
        g = QGroupBox("📡  Ultrasónicos")
        g.setStyleSheet(GS)
        l = QVBoxLayout(g)
        l.setSpacing(6)
        l.setContentsMargins(10, 6, 10, 6)

        bars = QHBoxLayout(); bars.setSpacing(12)
        self.us1 = _USBar("US1  Entrada")
        self.us2 = _USBar("US2  Cámara")
        bars.addWidget(self.us1)
        bars.addWidget(self.us2)
        l.addLayout(bars)

        ev_row = QHBoxLayout()
        ev_row.addWidget(QLabel("Evento:"))
        self.label_event = QLabel("—")
        self.label_event.setStyleSheet(
            "color:#ffa500; font-weight:bold; font-size:11px;")
        ev_row.addWidget(self.label_event)
        ev_row.addStretch()
        l.addLayout(ev_row)
        return g

    def _grp_log(self) -> QGroupBox:
        g = QGroupBox("🔍  Log del Pipeline")
        g.setStyleSheet(GS)
        l = QVBoxLayout(g)
        l.setSpacing(4)
        l.setContentsMargins(8, 6, 8, 6)

        self.det_log = QTextEdit()
        self.det_log.setReadOnly(True)
        self.det_log.setFixedHeight(120)
        self.det_log.setFont(QFont("Consolas", 9))
        self.det_log.setStyleSheet(
            "QTextEdit{background:#0d1117;color:#e6db74;"
            "border:1px solid #30363d;border-radius:4px;}")

        btn = QPushButton("Limpiar")
        btn.setFixedHeight(22)
        btn.clicked.connect(self.det_log.clear)

        l.addWidget(self.det_log)
        l.addWidget(btn)
        return g

    def _grp_save(self) -> QGroupBox:
        g = QGroupBox("💾  Guardar detecciones")
        g.setStyleSheet(GS)
        l = QVBoxLayout(g)
        l.setSpacing(4)
        l.setContentsMargins(10, 6, 10, 6)

        self.chk_autosave = QCheckBox("Auto-guardar imagen + JSON")
        self.chk_autosave.setStyleSheet("color:#c9d1d9; font-size:11px;")

        row = QHBoxLayout(); row.setSpacing(6)
        self.label_save_path = QLabel(self._save_folder)
        self.label_save_path.setStyleSheet("color:#58a6ff; font-size:10px;")
        self.label_save_path.setWordWrap(True)
        self.btn_save_folder = QPushButton("📁")
        self.btn_save_folder.setFixedSize(24, 24)
        row.addWidget(self.label_save_path, stretch=1)
        row.addWidget(self.btn_save_folder)

        self.label_saved = QLabel("Guardadas: 0")
        self.label_saved.setStyleSheet("color:#8b949e; font-size:11px;")

        l.addWidget(self.chk_autosave)
        l.addLayout(row)
        l.addWidget(self.label_saved)
        return g

    def _grp_machine(self) -> QGroupBox:
        self.grp_machine_box = QGroupBox("🤖  Máquina  —  ESP32")
        self.grp_machine_box.setStyleSheet(GS)
        self.grp_machine_box.setEnabled(False)

        g = self.grp_machine_box
        l = QVBoxLayout(g)
        l.setSpacing(4)
        l.setContentsMargins(10, 6, 10, 8)

        # Banda
        l.addWidget(_sec("Banda  (NEMA17)"))
        r1 = QHBoxLayout(); r1.setSpacing(6)
        self.btn_belt_on  = QPushButton("▶ ON");  self.btn_belt_on.setStyleSheet(BGRN)
        self.btn_belt_off = QPushButton("■ OFF"); self.btn_belt_off.setStyleSheet(BORG)
        self.btn_belt_on.setFixedHeight(24)
        self.btn_belt_off.setFixedHeight(24)
        r1.addWidget(self.btn_belt_on); r1.addWidget(self.btn_belt_off)
        l.addLayout(r1)

        rs = QHBoxLayout(); rs.setSpacing(6)
        self.sld_spd = QSlider(Qt.Horizontal)
        self.sld_spd.setRange(100, 3000); self.sld_spd.setValue(800)
        self.lbl_spd = QLabel("800"); self.lbl_spd.setFixedWidth(32)
        self.sld_spd.valueChanged.connect(lambda v: self.lbl_spd.setText(str(v)))
        self.btn_spd_ok = QPushButton("OK")
        self.btn_spd_ok.setFixedWidth(28); self.btn_spd_ok.setFixedHeight(22)
        rs.addWidget(QLabel("spd:"))
        rs.addWidget(self.sld_spd)
        rs.addWidget(self.lbl_spd)
        rs.addWidget(self.btn_spd_ok)
        l.addLayout(rs)
        l.addWidget(_sep())

        # Sorting
        l.addWidget(_sec("Sorting  (NEMA17)"))
        r2 = QHBoxLayout(); r2.setSpacing(6)
        self.btn_s0 = QPushButton("0");      self.btn_s0.setStyleSheet(BGRY)
        self.btn_s1 = QPushButton("1 BOT");  self.btn_s1.setStyleSheet(BBLU)
        self.btn_s2 = QPushButton("2 LATA"); self.btn_s2.setStyleSheet(BPUR)
        for b in (self.btn_s0, self.btn_s1, self.btn_s2):
            b.setFixedHeight(26)
        r2.addWidget(self.btn_s0); r2.addWidget(self.btn_s1); r2.addWidget(self.btn_s2)
        l.addLayout(r2)
        self.btn_home = QPushButton("⌂  Home")
        self.btn_home.setFixedHeight(24)
        l.addWidget(self.btn_home)
        l.addWidget(_sep())

        # Servos
        l.addWidget(_sec("Servos"))
        for idx, (attr_o, attr_c) in enumerate(
                [("btn_s1o", "btn_s1c"), ("btn_s2o", "btn_s2c")], start=1):
            row = QHBoxLayout(); row.setSpacing(6)
            row.addWidget(QLabel(f"S{idx}:"))
            bo = QPushButton("↕ Open");  bo.setStyleSheet(BGRN); bo.setFixedHeight(24)
            bc = QPushButton("⊟ Close"); bc.setStyleSheet(BORG); bc.setFixedHeight(24)
            setattr(self, attr_o, bo)
            setattr(self, attr_c, bc)
            row.addWidget(bo); row.addWidget(bc)
            l.addLayout(row)
        l.addWidget(_sep())

        # ── E-STOP  (siempre visible aunque el grupo esté disabled) ───────
        # Lo añadimos FUERA del grupo para que sea siempre accesible
        return g

    # ──────────────────────────────────────────────────────────────────────
    # Botón E-STOP independiente del grupo (siempre activo)
    def _build_estop_row(self) -> QPushButton:
        self.btn_estop = QPushButton("🛑  PARO DE EMERGENCIA")
        self.btn_estop.setFixedHeight(36)
        self.btn_estop.setStyleSheet("""
            QPushButton {
                background:#b91c1c; color:#fff; font-weight:bold;
                border-radius:6px; font-size:13px;
                border:2px solid #ef4444;
            }
            QPushButton:hover   { background:#dc2626; }
            QPushButton:pressed { background:#7f1d1d; }
        """)
        return self.btn_estop

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(4)
        root.setContentsMargins(6, 6, 6, 6)

        # ── Barra superior ────────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(8)

        self.btn_start = QPushButton("▶  START DETECCIÓN")
        self.btn_start.setFixedHeight(32)
        self.btn_start.setEnabled(False)
        self.btn_start.setStyleSheet(BTN_START_OFF)

        mode_box = QGroupBox("Modo")
        mode_box.setFixedWidth(160)
        mode_box.setStyleSheet("""
            QGroupBox { border:1px solid #30363d; border-radius:6px;
                        font-size:10px; color:#8b949e;
                        margin-top:6px; padding-top:2px; }
            QGroupBox::title { subcontrol-origin:margin; left:8px; }
        """)
        ml = QHBoxLayout(mode_box)
        ml.setContentsMargins(6, 2, 6, 2); ml.setSpacing(10)
        self.radio_auto   = QRadioButton("AUTO")
        self.radio_manual = QRadioButton("MANUAL")
        self.radio_manual.setChecked(True)
        for r in (self.radio_auto, self.radio_manual):
            r.setStyleSheet("color:#c9d1d9; font-weight:bold; font-size:12px;")
        ml.addWidget(self.radio_auto); ml.addWidget(self.radio_manual)

        top.addWidget(self.btn_start, stretch=1)
        top.addWidget(mode_box)
        root.addLayout(top, 0)

        # ── Splitter ──────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(5)
        splitter.setStyleSheet("""
            QSplitter::handle { background:#21262d; border-radius:2px; }
            QSplitter::handle:hover { background:#30363d; }
        """)

        # Zona izquierda
        left_w = QWidget()
        left_l = QVBoxLayout(left_w)
        left_l.setContentsMargins(0, 0, 0, 0); left_l.setSpacing(6)

        self.video = VideoLabel("📷  Conecta la cámara y carga los modelos")
        self.video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.label_info = QLabel("Estado: idle  |  Detecciones: —")
        self.label_info.setAlignment(Qt.AlignCenter)
        self.label_info.setFixedHeight(24)
        self.label_info.setStyleSheet(INFO_IDLE)

        left_l.addWidget(self.video, stretch=1)
        left_l.addWidget(self.label_info, stretch=0)
        left_l.addWidget(self._build_gallery(), stretch=0)

        # Zona derecha
        right_w = QWidget()
        right_w.setMinimumWidth(320)
        right_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border:none; background:transparent; }
            QScrollBar:vertical { background:#0d1117; width:5px; border-radius:2px; }
            QScrollBar::handle:vertical { background:#30363d; border-radius:2px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
        """)

        inner = QWidget()
        inner_l = QVBoxLayout(inner)
        inner_l.setSpacing(8)
        inner_l.setContentsMargins(6, 4, 6, 6)

        inner_l.addWidget(self._grp_pipeline())
        inner_l.addWidget(self._grp_ultrasonics())
        inner_l.addWidget(self._grp_log())
        inner_l.addWidget(self._grp_save())
        inner_l.addWidget(self._grp_machine())
        # E-STOP siempre visible y fuera del grupo deshabilitable
        inner_l.addWidget(self._build_estop_row())
        inner_l.addStretch()

        scroll.setWidget(inner)

        rlay = QVBoxLayout(right_w)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.addWidget(scroll)

        splitter.addWidget(left_w)
        splitter.addWidget(right_w)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([600, 400])

        root.addWidget(splitter, 1)

    # ──────────────────────────────────────────────────────────────────────
    def _connect_signals(self):
        self._worker.result_ready.connect(self._on_result)
        self._worker.error.connect(
            lambda msg: self.status_message.emit(f"⚠️ {msg}"))

        self.btn_start.clicked.connect(self._toggle_start)
        self.radio_auto.toggled.connect(lambda v: setattr(self, '_auto', v))
        self.btn_open_pipe.clicked.connect(self._show_pipeline_dialog)

        self._serial.us_data.connect(self._on_us)
        self._serial.event_received.connect(self._on_event)

        self.btn_save_folder.clicked.connect(self._pick_save_folder)

        # Máquina
        self.btn_belt_on.clicked.connect(self._serial.belt_start)
        self.btn_belt_off.clicked.connect(self._serial.belt_stop)
        self.btn_spd_ok.clicked.connect(
            lambda: self._serial.belt_speed(self.sld_spd.value()))
        self.btn_s0.clicked.connect(lambda: self._serial.sort(0))
        self.btn_s1.clicked.connect(lambda: self._serial.sort(1))
        self.btn_s2.clicked.connect(lambda: self._serial.sort(2))
        self.btn_home.clicked.connect(self._serial.sort_home)
        self.btn_s1o.clicked.connect(self._serial.servo1_open)
        self.btn_s1c.clicked.connect(self._serial.servo1_close)
        self.btn_s2o.clicked.connect(self._serial.servo2_open)
        self.btn_s2c.clicked.connect(self._serial.servo2_close)

        # E-STOP: botón + atajos de teclado (Space / Escape)
        self.btn_estop.clicked.connect(self._serial.emergency_stop)
        self.shortcut_space = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.shortcut_space.activated.connect(self._serial.emergency_stop)
        self.shortcut_esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.shortcut_esc.activated.connect(self._serial.emergency_stop)

    # ── Pipeline dialog ───────────────────────────────────────────────────
    def _show_pipeline_dialog(self):
        if self._pipeline_dlg is None:
            self._pipeline_dlg = PipelineDialog(
                self._worker, self._worker._config_path, self)
            if self.window():
                self._pipeline_dlg.setStyleSheet(self.window().styleSheet())
        self._pipeline_dlg.show()
        self._pipeline_dlg.raise_()
        self._pipeline_dlg.activateWindow()

    # ── Slots públicos ────────────────────────────────────────────────────
    def receive_frame(self, frame: np.ndarray):
        self._last_frame = frame
        if self._running:
            self._worker.submit_frame(frame)
        else:
            self.video.display_frame(frame)

    def on_camera_connected(self, idx: int):
        if not self._worker.isRunning():
            self._worker.start()
        self.btn_start.setEnabled(True)

    def on_camera_disconnected(self):
        self._stop_detection()
        self.video.clear_frame()
        self.btn_start.setEnabled(False)

    # ── START / STOP ──────────────────────────────────────────────────────
    def _toggle_start(self):
        if self._running:
            self._stop_detection()
        else:
            self._start_detection()

    def _start_detection(self):
        self._running = True
        self._auto    = self.radio_auto.isChecked()
        self.btn_start.setText("■  STOP DETECCIÓN")
        self.btn_start.setStyleSheet(BTN_START_ON)
        self.radio_auto.setEnabled(False)
        self.radio_manual.setEnabled(False)
        self.grp_machine_box.setEnabled(True)
        mode = "AUTO 🤖" if self._auto else "MANUAL 🖐"
        self.label_info.setText(f"▶  Detectando en cascada...  |  Modo: {mode}")
        self.label_info.setStyleSheet(INFO_RUN)
        self.status_message.emit(f"▶  Detección iniciada — {mode}")

    def _stop_detection(self):
        self._running = False
        self._auto    = False
        self.btn_start.setText("▶  START DETECCIÓN")
        self.btn_start.setStyleSheet(BTN_START_OFF)
        self.radio_auto.setEnabled(True)
        self.radio_manual.setEnabled(True)
        self.grp_machine_box.setEnabled(False)
        # FIX: NO enviar E_STOP en stop normal — el ESP32 sigue su ciclo
        # Si se necesita parar la máquina, usar el botón E-STOP explícitamente
        self.label_info.setText("Estado: idle  |  Detecciones: —")
        self.label_info.setStyleSheet(INFO_IDLE)
        self.status_message.emit("■  Detección detenida")

    # ── Resultado del pipeline ────────────────────────────────────────────
    def _on_result(self, result: PipelineResult):
        if not self._running:
            return

        if result.annotated is not None:
            self.video.display_frame(result.annotated)

        mode      = "AUTO 🤖" if self._auto else "MANUAL 🖐"
        main_type = result.type

        if result.stopped_at:
            self.label_info.setText(
                f"🛑 Detenido en [{result.stopped_at}]  |  {mode}")
        else:
            self.label_info.setText(f"▶ Analizado: {main_type}  |  {mode}")

        if result.steps:
            ts = datetime.now().strftime("%H:%M:%S")
            self.det_log.append(f"--- Análisis {ts} ---")
            for step in result.steps:
                if step.label != "desconocido":
                    self.det_log.append(
                        f" > {step.model_id}: {step.label} ({step.conf:.2f})")
            if result.price_mxn > 0:
                self.det_log.append(
                    f" 💰 Valor estimado: ${result.price_mxn:.2f} MXN")
            self.det_log.verticalScrollBar().setValue(
                self.det_log.verticalScrollBar().maximum())

            if self.chk_autosave.isChecked() and result.annotated is not None:
                self._save_detection(result)

            if self._auto and self._pending_auto_sort:
                cls_id = self.CLASS_SORT_MAP.get(main_type, 0)
                self._serial.sort(cls_id)
                self.det_log.append(f"[AUTO] → SORT:{cls_id}  ({main_type})")
                self._pending_auto_sort = False

    # ── Guardado ──────────────────────────────────────────────────────────
    def _save_detection(self, result: PipelineResult):
        os.makedirs(self._save_folder, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
        base = f"{ts}_{result.type}"

        cv2.imwrite(
            os.path.join(self._save_folder, f"{base}.jpg"),
            result.annotated
        )

        steps_data = [
            {
                "model_id": s.model_id,
                "label":    s.label,
                "conf":     round(s.conf, 4),
                "bbox":     [round(v, 1) for v in s.bbox] if s.bbox else None,
            }
            for s in result.steps
        ]

        with open(os.path.join(self._save_folder, f"{base}.json"),
                  "w", encoding="utf-8") as f:
            json.dump({
                "timestamp":  datetime.now().isoformat(),
                "image":      f"{base}.jpg",
                "type":       result.type,
                "brand":      result.brand,
                "size":       result.size,
                "condition":  result.condition,
                "price_mxn":  result.price_mxn,
                "stopped_at": result.stopped_at,
                "steps":      steps_data,
            }, f, indent=2, ensure_ascii=False)

        self._add_to_gallery(result.annotated)
        self._saved_count += 1
        self.label_saved.setText(f"Guardadas: {self._saved_count}")
        self.status_message.emit(f"💾  {base}.jpg")

    def _pick_save_folder(self):
        f = QFileDialog.getExistingDirectory(self, "Carpeta detecciones")
        if f:
            self._save_folder = f
            self.label_save_path.setText(f)

    # ── Sensores ultrasónicos ─────────────────────────────────────────────
    def _on_us(self, d1: int, d2: int):
        self.us1.update(d1)
        self.us2.update(d2)

    def _on_event(self, event: str):
        self.label_event.setText(event)
        self.det_log.append(f"[ESP32] {event}")
        if event == "OBJ_AT_CAM" and self._running and self._auto:
            self._pending_auto_sort = True
            self.det_log.append("[AUTO] Objeto en cámara → detectando…")


# ─── Helpers ─────────────────────────────────────────────────────────────
def _sec(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet("color:#484f58; font-size:10px; margin-top:2px;")
    return l

def _sep() -> QFrame:
    s = QFrame(); s.setFrameShape(QFrame.HLine)
    s.setStyleSheet("color:#21262d;"); return s


# ─── Estilos ─────────────────────────────────────────────────────────────
GS = """
QGroupBox { font-weight:bold; font-size:12px; color:#c9d1d9;
            border:1px solid #30363d; border-radius:8px;
            margin-top:8px; padding-top:6px; padding-bottom:4px; }
QGroupBox::title { subcontrol-origin:margin; left:10px; top:-2px; padding:0 4px; }
"""
INFO_IDLE = ("color:#484f58; font-size:12px; font-family:Consolas; "
             "background:#0d1117; border:1px solid #21262d; "
             "border-radius:4px; padding:4px 8px;")
INFO_RUN  = ("color:#00d4aa; font-size:12px; font-family:Consolas; "
             "background:#0d1117; border:1px solid #00d4aa; "
             "border-radius:4px; padding:4px 8px;")
BTN_PRIMARY   = ("QPushButton{background:#1f6feb;color:#fff;border-radius:5px;"
                 "font-weight:bold;padding:4px;} QPushButton:hover{background:#388bfd;}")
BTN_START_OFF = ("QPushButton{background:#196c2e;color:#fff;font-weight:bold;"
                 "border-radius:7px;font-size:14px;}"
                 "QPushButton:hover{background:#238636;}"
                 "QPushButton:disabled{background:#1c2128;color:#484f58;"
                 "border:1px solid #30363d;}")
BTN_START_ON  = ("QPushButton{background:#7f1d1d;color:#fff;font-weight:bold;"
                 "border-radius:7px;font-size:14px;}"
                 "QPushButton:hover{background:#b91c1c;}")
BGRN = ("QPushButton{background:#196c2e;color:#fff;border-radius:4px;}"
        "QPushButton:hover{background:#238636;}")
BORG = ("QPushButton{background:#7d4e00;color:#fff;border-radius:4px;}"
        "QPushButton:hover{background:#bb6000;}")
BGRY = "QPushButton{background:#30363d;color:#c9d1d9;border-radius:4px;}"
BBLU = ("QPushButton{background:#1f6feb;color:#fff;border-radius:4px;}"
        "QPushButton:hover{background:#388bfd;}")
BPUR = ("QPushButton{background:#6e40c9;color:#fff;border-radius:4px;}"
        "QPushButton:hover{background:#8957e5;}")