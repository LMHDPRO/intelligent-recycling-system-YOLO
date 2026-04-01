"""
Tab de Detección v3.1 — layout fix:
  • Panel derecho con ancho fijo (290px) usando QSplitter
  • ScrollArea funcional con contenido compacto
  • Grupos de máquina reorganizados para caber bien
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
from PySide6.QtGui  import QFont

from core.yolo_worker    import YOLOWorker
from core.serial_manager import SerialManager
from ui.widgets          import VideoLabel


# ─── Barra ultrasónico ────────────────────────────────────────────────────
class _USBar(QWidget):
    MAX_CM = 100
    def __init__(self, title: str):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setSpacing(1)
        lay.setContentsMargins(0, 0, 0, 0)
        t = QLabel(title)
        t.setStyleSheet("color:#8b949e; font-size:9px;")
        t.setAlignment(Qt.AlignCenter)
        self._bar = QProgressBar()
        self._bar.setRange(0, self.MAX_CM)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(7)
        self._bar.setStyleSheet(_BAR.format(c="#00d4aa"))
        self._lbl = QLabel("—")
        self._lbl.setAlignment(Qt.AlignCenter)
        self._lbl.setStyleSheet(
            "color:#c9d1d9; font-size:10px; font-family:Consolas;")
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
        "botella_con_tapa": 1,
        "botella_sin_tapa": 1,
        "lata":             2,
        "ninguno":          0,
    }

    def __init__(self, yolo: YOLOWorker, serial: SerialManager):
        super().__init__()
        self._yolo   = yolo
        self._serial = serial
        self._running = False
        self._auto    = False
        self._pending_auto_sort = False
        self._save_folder  = os.path.join(os.getcwd(), "detections")
        self._saved_count  = 0
        self._last_frame: np.ndarray | None = None
        self._build_ui()
        self._connect_signals()

    # ──────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 8)

        # ── Barra superior: START + modo ──────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(8)

        self.btn_start = QPushButton("▶  START DETECCIÓN")
        self.btn_start.setFixedHeight(40)
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
            r.setStyleSheet(
                "color:#c9d1d9; font-weight:bold; font-size:12px;")
        ml.addWidget(self.radio_auto)
        ml.addWidget(self.radio_manual)

        top.addWidget(self.btn_start, stretch=1)
        top.addWidget(mode_box)
        root.addLayout(top)

        # ── Splitter horizontal: video | panel ────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet("""
            QSplitter::handle { background:#21262d; }
        """)

        # ── Izquierda: video ──────────────────────────────────────────────
        left_w = QWidget()
        left_l = QVBoxLayout(left_w)
        left_l.setContentsMargins(0, 0, 0, 0)
        left_l.setSpacing(4)

        self.video = VideoLabel("📷  Conecta la cámara y carga un modelo")
        self.video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.label_info = QLabel("Estado: idle  |  Detecciones: —")
        self.label_info.setAlignment(Qt.AlignCenter)
        self.label_info.setFixedHeight(24)
        self.label_info.setStyleSheet(INFO_IDLE)

        left_l.addWidget(self.video)
        left_l.addWidget(self.label_info)

        # ── Derecha: panel con scroll ─────────────────────────────────────
        right_w = QWidget()
        right_w.setFixedWidth(290)
        right_w.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

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
        inner_l.setSpacing(6)
        inner_l.setContentsMargins(4, 2, 4, 4)

        inner_l.addWidget(self._grp_model())
        inner_l.addWidget(self._grp_thresholds())
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
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([9999, 290])

        root.addWidget(splitter)

    # ── Grupos ────────────────────────────────────────────────────────────
    def _grp_model(self) -> QGroupBox:
        g = QGroupBox("🧠  Modelo YOLO"); g.setStyleSheet(GS)
        l = QVBoxLayout(g); l.setSpacing(4)
        self.label_model = QLabel("Sin modelo cargado")
        self.label_model.setWordWrap(True)
        self.label_model.setStyleSheet("color:#484f58; font-size:10px;")
        self.btn_load   = QPushButton("📂  Cargar modelo (.pt)")
        self.btn_load.setStyleSheet(BTN_PRIMARY)
        self.btn_unload = QPushButton("✕  Descargar")
        self.btn_unload.setEnabled(False)
        l.addWidget(self.label_model)
        l.addWidget(self.btn_load)
        l.addWidget(self.btn_unload)
        return g

    def _grp_thresholds(self) -> QGroupBox:
        g = QGroupBox("⚙️  Umbrales"); g.setStyleSheet(GS)
        l = QFormLayout(g); l.setSpacing(5)
        l.setContentsMargins(8, 6, 8, 6)

        self.slider_conf = QSlider(Qt.Horizontal)
        self.slider_conf.setRange(1, 99); self.slider_conf.setValue(50)
        self.label_conf  = QLabel("0.50"); self.label_conf.setFixedWidth(32)
        r1 = QHBoxLayout()
        r1.addWidget(self.slider_conf); r1.addWidget(self.label_conf)
        l.addRow("Conf:", r1)

        self.slider_iou  = QSlider(Qt.Horizontal)
        self.slider_iou.setRange(1, 99); self.slider_iou.setValue(45)
        self.label_iou   = QLabel("0.45"); self.label_iou.setFixedWidth(32)
        r2 = QHBoxLayout()
        r2.addWidget(self.slider_iou); r2.addWidget(self.label_iou)
        l.addRow("IOU:", r2)
        return g

    def _grp_ultrasonics(self) -> QGroupBox:
        g = QGroupBox("📡  Ultrasónicos"); g.setStyleSheet(GS)
        l = QVBoxLayout(g); l.setSpacing(4)
        l.setContentsMargins(8, 6, 8, 6)

        bars = QHBoxLayout(); bars.setSpacing(8)
        self.us1 = _USBar("US1  Entrada")
        self.us2 = _USBar("US2  Cámara")
        bars.addWidget(self.us1); bars.addWidget(self.us2)
        l.addLayout(bars)

        ev_row = QHBoxLayout()
        ev_row.addWidget(QLabel("Evento:"))
        self.label_event = QLabel("—")
        self.label_event.setStyleSheet(
            "color:#ffa500; font-weight:bold; font-size:10px;")
        ev_row.addWidget(self.label_event)
        ev_row.addStretch()
        l.addLayout(ev_row)
        return g

    def _grp_log(self) -> QGroupBox:
        g = QGroupBox("🔍  Log detecciones"); g.setStyleSheet(GS)
        l = QVBoxLayout(g); l.setSpacing(3)
        l.setContentsMargins(6, 6, 6, 6)
        self.det_log = QTextEdit()
        self.det_log.setReadOnly(True)
        self.det_log.setFixedHeight(90)
        self.det_log.setFont(QFont("Consolas", 9))
        self.det_log.setStyleSheet(
            "QTextEdit{background:#0d1117;color:#e6db74;"
            "border:1px solid #30363d;border-radius:4px;}")
        btn = QPushButton("Limpiar")
        btn.setFixedHeight(20)
        btn.clicked.connect(self.det_log.clear)
        l.addWidget(self.det_log); l.addWidget(btn)
        return g

    def _grp_save(self) -> QGroupBox:
        g = QGroupBox("💾  Guardar detecciones"); g.setStyleSheet(GS)
        l = QVBoxLayout(g); l.setSpacing(4)
        l.setContentsMargins(8, 6, 8, 6)
        self.chk_autosave = QCheckBox("Auto-guardar imagen + JSON")
        self.chk_autosave.setStyleSheet("color:#c9d1d9; font-size:11px;")
        row = QHBoxLayout(); row.setSpacing(4)
        self.label_save_path = QLabel(self._save_folder)
        self.label_save_path.setStyleSheet(
            "color:#58a6ff; font-size:9px;")
        self.label_save_path.setWordWrap(True)
        self.btn_save_folder = QPushButton("📁")
        self.btn_save_folder.setFixedSize(24, 24)
        row.addWidget(self.label_save_path, stretch=1)
        row.addWidget(self.btn_save_folder)
        self.label_saved = QLabel("Guardadas: 0")
        self.label_saved.setStyleSheet("color:#8b949e; font-size:10px;")
        l.addWidget(self.chk_autosave)
        l.addLayout(row)
        l.addWidget(self.label_saved)
        return g

    def _grp_machine(self) -> QGroupBox:
        g = QGroupBox("🤖  Máquina  —  ESP32"); g.setStyleSheet(GS)
        l = QVBoxLayout(g); l.setSpacing(4)
        l.setContentsMargins(8, 6, 8, 8)

        # Banda
        l.addWidget(_sec("Banda  (NEMA17)"))
        r1 = QHBoxLayout(); r1.setSpacing(4)
        self.btn_belt_on  = QPushButton("▶ ON");  self.btn_belt_on.setStyleSheet(BGRN)
        self.btn_belt_off = QPushButton("■ OFF"); self.btn_belt_off.setStyleSheet(BORG)
        r1.addWidget(self.btn_belt_on); r1.addWidget(self.btn_belt_off)
        l.addLayout(r1)

        rs = QHBoxLayout(); rs.setSpacing(4)
        self.sld_spd = QSlider(Qt.Horizontal)
        self.sld_spd.setRange(100, 3000); self.sld_spd.setValue(800)
        self.lbl_spd = QLabel("800"); self.lbl_spd.setFixedWidth(32)
        self.sld_spd.valueChanged.connect(lambda v: self.lbl_spd.setText(str(v)))
        self.btn_spd_ok = QPushButton("OK"); self.btn_spd_ok.setFixedWidth(26)
        rs.addWidget(QLabel("spd:")); rs.addWidget(self.sld_spd)
        rs.addWidget(self.lbl_spd); rs.addWidget(self.btn_spd_ok)
        l.addLayout(rs)
        l.addWidget(_sep())

        # Sorting
        l.addWidget(_sec("Sorting  (NEMA17)"))
        r2 = QHBoxLayout(); r2.setSpacing(4)
        self.btn_s0 = QPushButton("0");       self.btn_s0.setStyleSheet(BGRY)
        self.btn_s1 = QPushButton("1 BOT");   self.btn_s1.setStyleSheet(BBLU)
        self.btn_s2 = QPushButton("2 LATA");  self.btn_s2.setStyleSheet(BPUR)
        for b in (self.btn_s0, self.btn_s1, self.btn_s2):
            b.setFixedHeight(26)
        r2.addWidget(self.btn_s0); r2.addWidget(self.btn_s1); r2.addWidget(self.btn_s2)
        l.addLayout(r2)
        self.btn_home = QPushButton("⌂  Home")
        self.btn_home.setFixedHeight(24)
        l.addWidget(self.btn_home)
        l.addWidget(_sep())

        # Servos — 2 filas compactas
        l.addWidget(_sec("Servos"))
        for idx, (attr_o, attr_c) in enumerate(
                [("btn_s1o", "btn_s1c"), ("btn_s2o", "btn_s2c")], start=1):
            row = QHBoxLayout(); row.setSpacing(4)
            row.addWidget(QLabel(f"S{idx}:"))
            bo = QPushButton("↕ Open");  bo.setStyleSheet(BGRN); bo.setFixedHeight(24)
            bc = QPushButton("⊟ Close"); bc.setStyleSheet(BORG); bc.setFixedHeight(24)
            setattr(self, attr_o, bo); setattr(self, attr_c, bc)
            row.addWidget(bo); row.addWidget(bc)
            l.addLayout(row)
        l.addWidget(_sep())

        # E-STOP
        self.btn_estop = QPushButton("🛑  PARO DE EMERGENCIA")
        self.btn_estop.setFixedHeight(34)
        self.btn_estop.setStyleSheet(BESTOP)
        l.addWidget(self.btn_estop)
        return g

    # ──────────────────────────────────────────────────────────────────────
    def _connect_signals(self):
        self.btn_load.clicked.connect(self._load_model)
        self.btn_unload.clicked.connect(self._unload_model)
        self._yolo.model_loaded.connect(self._on_model_loaded)
        self._yolo.result_ready.connect(self._on_result)

        self.btn_start.clicked.connect(self._toggle_start)
        self.radio_auto.toggled.connect(lambda v: setattr(self, '_auto', v))

        self.slider_conf.valueChanged.connect(
            lambda v: (self.label_conf.setText(f"{v/100:.2f}"),
                       self._yolo.set_confidence(v / 100)))
        self.slider_iou.valueChanged.connect(
            lambda v: (self.label_iou.setText(f"{v/100:.2f}"),
                       self._yolo.set_iou(v / 100)))

        self._serial.us_data.connect(self._on_us)
        self._serial.event_received.connect(self._on_event)

        self.btn_save_folder.clicked.connect(self._pick_save_folder)

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
        self.btn_estop.clicked.connect(self._serial.emergency_stop)

    # ── Slots públicos ────────────────────────────────────────────────────
    def receive_frame(self, frame: np.ndarray):
        self._last_frame = frame
        if self._running:
            self._yolo.submit_frame(frame)
        else:
            self.video.display_frame(frame)

    def on_camera_connected(self, idx: int):
        if not self._yolo.isRunning():
            self._yolo.start()
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
        mode = "AUTO 🤖" if self._auto else "MANUAL 🖐"
        self.label_info.setText(f"▶  Detectando  |  Modo: {mode}")
        self.label_info.setStyleSheet(INFO_RUN)
        self.status_message.emit(f"▶  Detección iniciada — {mode}")

    def _stop_detection(self):
        self._running = False
        self._auto    = False
        self.btn_start.setText("▶  START DETECCIÓN")
        self.btn_start.setStyleSheet(BTN_START_OFF)
        self.radio_auto.setEnabled(True)
        self.radio_manual.setEnabled(True)
        self.label_info.setText("Estado: idle  |  Detecciones: —")
        self.label_info.setStyleSheet(INFO_IDLE)
        self.status_message.emit("■  Detección detenida")

    # ── Modelo ────────────────────────────────────────────────────────────
    def _load_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Modelo YOLO", os.getcwd(), "YOLO (*.pt *.onnx);;All (*)")
        if path:
            self.label_model.setText(f"⏳  {os.path.basename(path)}…")
            self._yolo.load_model(path)

    def _unload_model(self):
        self._yolo.unload_model()

    def _on_model_loaded(self, ok: bool, msg: str):
        self.label_model.setText(msg)
        self.label_model.setStyleSheet(
            f"color:{'#00d4aa' if ok else '#ff4757'}; font-size:10px;")
        self.btn_unload.setEnabled(ok)
        self.status_message.emit(msg)

    # ── Resultado YOLO ────────────────────────────────────────────────────
    def _on_result(self, frame: np.ndarray, detections: list):
        if not self._running:
            return
        self.video.display_frame(frame)
        n = len(detections)
        mode = "AUTO 🤖" if self._auto else "MANUAL 🖐"
        self.label_info.setText(
            f"▶  Detectando  |  {n} obj  |  {mode}")

        if detections:
            ts = datetime.now().strftime("%H:%M:%S")
            for d in detections:
                self.det_log.append(
                    f"[{ts}] {d['name']:18s}  {d['conf']:.2f}")
            self.det_log.verticalScrollBar().setValue(
                self.det_log.verticalScrollBar().maximum())

            if self.chk_autosave.isChecked():
                self._save_detection(frame, detections)

            if self._auto and self._pending_auto_sort:
                best   = max(detections, key=lambda d: d["conf"])
                cls_id = self.CLASS_SORT_MAP.get(best["name"], 0)
                self._serial.sort(cls_id)
                self.det_log.append(
                    f"[AUTO] → SORT:{cls_id}  ({best['name']})")
                self._pending_auto_sort = False

    # ── Guardado ──────────────────────────────────────────────────────────
    def _save_detection(self, frame: np.ndarray, detections: list):
        os.makedirs(self._save_folder, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
        d0   = detections[0]
        base = f"{ts}_{d0['name']}_{int(d0['conf']*100)}"
        cv2.imwrite(os.path.join(self._save_folder, f"{base}.jpg"), frame)
        with open(os.path.join(self._save_folder, f"{base}.json"), "w") as f:
            json.dump({
                "timestamp":  datetime.now().isoformat(),
                "image":      f"{base}.jpg",
                "detections": [
                    {"class_id": d["class_id"], "name": d["name"],
                     "conf": round(d["conf"], 4),
                     "xyxy": [round(v, 1) for v in d["xyxy"]]}
                    for d in detections
                ]
            }, f, indent=2)
        self._saved_count += 1
        self.label_saved.setText(f"Guardadas: {self._saved_count}")
        self.status_message.emit(f"💾  {base}.jpg")

    def _pick_save_folder(self):
        f = QFileDialog.getExistingDirectory(self, "Carpeta detecciones")
        if f:
            self._save_folder = f
            self.label_save_path.setText(f)

    # ── Sensores ──────────────────────────────────────────────────────────
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
    l.setStyleSheet(
        "color:#484f58; font-size:9px; margin-top:1px;")
    return l

def _sep() -> QFrame:
    s = QFrame(); s.setFrameShape(QFrame.HLine)
    s.setStyleSheet("color:#21262d;"); return s


# ─── Estilos ─────────────────────────────────────────────────────────────
GS = """
QGroupBox { font-weight:bold; font-size:11px; color:#c9d1d9;
            border:1px solid #30363d; border-radius:7px;
            margin-top:6px; padding-top:5px; }
QGroupBox::title { subcontrol-origin:margin; left:9px; padding:0 4px; }
"""
INFO_IDLE = ("color:#484f58; font-size:11px; font-family:Consolas; "
             "background:#0d1117; border:1px solid #21262d; "
             "border-radius:4px; padding:2px 6px;")
INFO_RUN  = ("color:#00d4aa; font-size:11px; font-family:Consolas; "
             "background:#0d1117; border:1px solid #00d4aa; "
             "border-radius:4px; padding:2px 6px;")
BTN_PRIMARY  = ("QPushButton{background:#1f6feb;color:#fff;border-radius:5px;"
                "font-weight:bold;padding:4px;} QPushButton:hover{background:#388bfd;}")
BTN_START_OFF = ("QPushButton{background:#196c2e;color:#fff;font-weight:bold;"
                 "border-radius:7px;font-size:14px;}"
                 "QPushButton:hover{background:#238636;}"
                 "QPushButton:disabled{background:#1c2128;color:#484f58;"
                 "border:1px solid #30363d;}")
BTN_START_ON  = ("QPushButton{background:#7f1d1d;color:#fff;font-weight:bold;"
                 "border-radius:7px;font-size:14px;}"
                 "QPushButton:hover{background:#b91c1c;}")
BGRN  = ("QPushButton{background:#196c2e;color:#fff;border-radius:4px;}"
         "QPushButton:hover{background:#238636;}")
BORG  = ("QPushButton{background:#7d4e00;color:#fff;border-radius:4px;}"
         "QPushButton:hover{background:#bb6000;}")
BGRY  = "QPushButton{background:#30363d;color:#c9d1d9;border-radius:4px;}"
BBLU  = ("QPushButton{background:#1f6feb;color:#fff;border-radius:4px;}"
         "QPushButton:hover{background:#388bfd;}")
BPUR  = ("QPushButton{background:#6e40c9;color:#fff;border-radius:4px;}"
         "QPushButton:hover{background:#8957e5;}")
BESTOP = ("QPushButton{background:#b91c1c;color:#fff;font-weight:bold;"
          "border-radius:6px;font-size:12px;}"
          "QPushButton:hover{background:#ef4444;}")

from PySide6.QtWidgets import QHBoxLayout