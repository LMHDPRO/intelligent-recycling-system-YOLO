"""
Tab de Captura de Dataset v2:
  • Dropdowns editables de lote y clase con ➕ botón "Guardar nuevo"
  • Presets persistentes en capture_presets.json (carpeta del script)
  • Preview de cámara mejorado
  • Panel de control más cómodo
"""
import os
import json
import cv2
import numpy as np
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
    QLabel, QComboBox, QPushButton, QSpinBox,
    QProgressBar, QFileDialog, QMessageBox,
    QSizePolicy, QFormLayout, QFrame, QLineEdit,
    QInputDialog, QToolButton
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui  import QFont, QIcon

from ui.widgets import VideoLabel

# ── Archivo de presets ─────────────────────────────────────────────────────
_PRESETS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "capture_presets.json")

_DEFAULT_CLASSES = [
    "botella_con_tapa",
    "botella_sin_tapa",
    "lata",
    "ninguno",
]
_DEFAULT_BATCHES = ["lote_01", "lote_02"]


def _load_presets() -> dict:
    try:
        with open(_PRESETS_FILE) as f:
            return json.load(f)
    except Exception:
        return {
            "classes": list(_DEFAULT_CLASSES),
            "batches": list(_DEFAULT_BATCHES),
            "last_folder": os.path.join(os.getcwd(), "dataset"),
            "quantity":    20,
            "interval_ms": 500,
        }


def _save_presets(data: dict):
    try:
        with open(_PRESETS_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────
class _EditableCombo(QWidget):
    """ComboBox editable con botón ➕ para añadir y 🗑 para borrar."""

    changed = Signal(str)

    def __init__(self, items: list[str], placeholder: str = ""):
        super().__init__()
        self._items = list(items)

        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.NoInsert)
        self.combo.lineEdit().setPlaceholderText(placeholder)
        self._populate()

        self.btn_add = QToolButton()
        self.btn_add.setText("➕")
        self.btn_add.setToolTip("Guardar texto actual como nueva opción")
        self.btn_add.setFixedSize(28, 28)

        self.btn_del = QToolButton()
        self.btn_del.setText("🗑")
        self.btn_del.setToolTip("Eliminar opción seleccionada")
        self.btn_del.setFixedSize(28, 28)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        lay.addWidget(self.combo)
        lay.addWidget(self.btn_add)
        lay.addWidget(self.btn_del)

        self.btn_add.clicked.connect(self._add_item)
        self.btn_del.clicked.connect(self._del_item)
        self.combo.currentTextChanged.connect(self.changed)

    def _populate(self):
        self.combo.clear()
        for item in self._items:
            self.combo.addItem(item)

    def _add_item(self):
        text = self.combo.currentText().strip()
        if not text or text in self._items:
            return
        self._items.append(text)
        self.combo.addItem(text)
        self.combo.setCurrentText(text)

    def _del_item(self):
        text = self.combo.currentText().strip()
        if text in self._items and len(self._items) > 1:
            self._items.remove(text)
            idx = self.combo.currentIndex()
            self.combo.removeItem(idx)

    def current_text(self) -> str:
        return self.combo.currentText().strip()

    def get_items(self) -> list[str]:
        return list(self._items)

    def set_items(self, items: list[str]):
        self._items = list(items)
        self._populate()


# ─────────────────────────────────────────────────────────────────────────
class CaptureTab(QWidget):
    status_message = Signal(str)

    def __init__(self):
        super().__init__()
        self._last_frame: np.ndarray | None = None
        self._burst_count  = 0
        self._burst_total  = 0
        self._burst_timer  = QTimer(self)
        self._burst_timer.timeout.connect(self._take_one)
        self._presets      = _load_presets()
        self._save_folder  = self._presets.get(
            "last_folder", os.path.join(os.getcwd(), "dataset"))
        self._build_ui()
        self._connect_signals()

    # ──────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(12, 12, 12, 12)

        # Izquierda: preview
        left = QVBoxLayout()
        self.video = VideoLabel("📷  Conecta la cámara en Configuración")
        self.video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.label_cam_info = QLabel("Sin cámara activa")
        self.label_cam_info.setAlignment(Qt.AlignCenter)
        self.label_cam_info.setStyleSheet("color:#484f58; font-size:11px;")
        left.addWidget(self.video)
        left.addWidget(self.label_cam_info)

        # Derecha: controles
        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(self._build_folder_group())
        right.addWidget(self._build_capture_group())
        right.addWidget(self._build_progress_group())
        right.addWidget(self._build_stats_group())
        right.addStretch()

        root.addLayout(left, stretch=3)
        root.addLayout(right, stretch=1)

    # ── Grupos ────────────────────────────────────────────────────────────
    def _build_folder_group(self) -> QGroupBox:
        g = QGroupBox("📁  Carpeta de salida")
        g.setStyleSheet(GROUP_STYLE)
        lay = QVBoxLayout(g)
        lay.setSpacing(4)
        self.label_folder = QLabel(self._save_folder)
        self.label_folder.setWordWrap(True)
        self.label_folder.setStyleSheet(
            "color:#58a6ff; font-size:10px; padding:2px;")
        self.btn_folder = QPushButton("📂  Seleccionar carpeta…")
        self.btn_folder.setFixedHeight(28)
        lay.addWidget(self.label_folder)
        lay.addWidget(self.btn_folder)
        return g

    def _build_capture_group(self) -> QGroupBox:
        g = QGroupBox("⚙️  Configuración de captura")
        g.setStyleSheet(GROUP_STYLE)
        lay = QFormLayout(g)
        lay.setSpacing(8)
        lay.setLabelAlignment(Qt.AlignRight)

        # Lote editable
        self.combo_batch = _EditableCombo(
            self._presets.get("batches", _DEFAULT_BATCHES),
            placeholder="nombre del lote…"
        )
        lay.addRow("Lote:", self.combo_batch)

        # Clase editable
        self.combo_class = _EditableCombo(
            self._presets.get("classes", _DEFAULT_CLASSES),
            placeholder="clase / etiqueta…"
        )
        lay.addRow("Clase:", self.combo_class)

        # Pista visual de la ruta
        self.label_dest_hint = QLabel("")
        self.label_dest_hint.setStyleSheet(
            "color:#484f58; font-size:9px; font-style:italic;")
        self.label_dest_hint.setWordWrap(True)
        lay.addRow("", self.label_dest_hint)
        self._update_dest_hint()

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#21262d;"); lay.addRow(sep)

        # Cantidad e intervalo
        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 1000)
        self.spin_qty.setValue(self._presets.get("quantity", 20))
        self.spin_qty.setSuffix("  fotos")
        lay.addRow("Cantidad:", self.spin_qty)

        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(100, 10000)
        self.spin_interval.setValue(self._presets.get("interval_ms", 500))
        self.spin_interval.setSuffix("  ms")
        self.spin_interval.setSingleStep(100)
        lay.addRow("Intervalo:", self.spin_interval)

        # Botón guardar configuración
        self.btn_save_preset = QPushButton("💾  Guardar configuración")
        self.btn_save_preset.setFixedHeight(26)
        self.btn_save_preset.setToolTip(
            "Guarda lotes, clases y parámetros en capture_presets.json")
        lay.addRow("", self.btn_save_preset)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color:#21262d;"); lay.addRow(sep2)

        # Botones de acción
        self.btn_burst = QPushButton("📸  TOMAR RÁFAGA")
        self.btn_burst.setFixedHeight(44)
        self.btn_burst.setEnabled(False)
        self.btn_burst.setStyleSheet(BTN_BURST)

        self.btn_stop  = QPushButton("■  Detener")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setFixedHeight(30)
        self.btn_stop.setStyleSheet(BTN_STOP)

        lay.addRow("", self.btn_burst)
        lay.addRow("", self.btn_stop)
        return g

    def _build_progress_group(self) -> QGroupBox:
        g = QGroupBox("📊  Progreso")
        g.setStyleSheet(GROUP_STYLE)
        lay = QVBoxLayout(g)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setStyleSheet("""
            QProgressBar { border:1px solid #30363d; border-radius:4px;
                           background:#161b22; color:#fff; text-align:center; height:16px; }
            QProgressBar::chunk { background:#00d4aa; border-radius:3px; }
        """)
        self.label_progress = QLabel("0 / 0")
        self.label_progress.setAlignment(Qt.AlignCenter)
        self.label_progress.setStyleSheet(
            "color:#c9d1d9; font-size:13px; font-family:Consolas;")
        lay.addWidget(self.progress)
        lay.addWidget(self.label_progress)
        return g

    def _build_stats_group(self) -> QGroupBox:
        g = QGroupBox("📈  Estadísticas")
        g.setStyleSheet(GROUP_STYLE)
        lay = QFormLayout(g)
        lay.setSpacing(5)
        self.label_total = QLabel("0")
        self.label_last  = QLabel("—")
        self.label_last.setStyleSheet("color:#58a6ff; font-size:10px;")
        lay.addRow("Total guardadas:", self.label_total)
        lay.addRow("Último archivo:", self.label_last)
        return g

    # ──────────────────────────────────────────────────────────────────────
    def _connect_signals(self):
        self.btn_folder.clicked.connect(self._select_folder)
        self.btn_burst.clicked.connect(self._start_burst)
        self.btn_stop.clicked.connect(self._stop_burst)
        self.btn_save_preset.clicked.connect(self._save_preset)

        self.combo_batch.changed.connect(lambda _: self._update_dest_hint())
        self.combo_class.changed.connect(lambda _: self._update_dest_hint())

    # ── Slots públicos ────────────────────────────────────────────────────
    def receive_frame(self, frame: np.ndarray):
        self._last_frame = frame
        self.video.display_frame(frame)

    def on_camera_connected(self, idx: int):
        self.label_cam_info.setText(f"Cámara {idx} activa  ✅")
        self.label_cam_info.setStyleSheet("color:#00d4aa; font-size:11px;")
        self.btn_burst.setEnabled(True)

    def on_camera_disconnected(self):
        self.label_cam_info.setText("Sin cámara activa")
        self.label_cam_info.setStyleSheet("color:#484f58; font-size:11px;")
        self.btn_burst.setEnabled(False)
        self.video.clear_frame()
        self._stop_burst()

    # ── Carpeta ───────────────────────────────────────────────────────────
    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Carpeta de salida", self._save_folder)
        if folder:
            self._save_folder = folder
            self.label_folder.setText(folder)
            self._update_dest_hint()

    def _update_dest_hint(self):
        batch = self.combo_batch.current_text() or "lote"
        cls   = self.combo_class.current_text() or "clase"
        short = os.path.join("…", batch, cls, "*.jpg")
        self.label_dest_hint.setText(short)

    # ── Presets ───────────────────────────────────────────────────────────
    def _save_preset(self):
        self._presets["classes"]     = self.combo_class.get_items()
        self._presets["batches"]     = self.combo_batch.get_items()
        self._presets["last_folder"] = self._save_folder
        self._presets["quantity"]    = self.spin_qty.value()
        self._presets["interval_ms"] = self.spin_interval.value()
        _save_presets(self._presets)
        self.status_message.emit("✅  Configuración guardada en capture_presets.json")

    # ── Ráfaga ────────────────────────────────────────────────────────────
    def _start_burst(self):
        if self._last_frame is None:
            QMessageBox.warning(self, "Sin cámara", "Conecta la cámara primero.")
            return

        batch    = self.combo_batch.current_text() or "lote_01"
        cls      = self.combo_class.current_text() or "sin_clase"
        total    = self.spin_qty.value()
        interval = self.spin_interval.value()

        dest = os.path.join(self._save_folder, batch, cls)
        os.makedirs(dest, exist_ok=True)
        self._dest_folder  = dest
        self._burst_count  = 0
        self._burst_total  = total

        self.progress.setMaximum(total)
        self.progress.setValue(0)
        self.label_progress.setText(f"0 / {total}")

        self.btn_burst.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._burst_timer.start(interval)
        self.status_message.emit(
            f"📸  Ráfaga iniciada — {batch}/{cls}  ({total} fotos, cada {interval}ms)")

    def _take_one(self):
        if self._last_frame is None or self._burst_count >= self._burst_total:
            self._stop_burst()
            return

        ts   = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
        name = f"{ts}_{self._burst_count:04d}.jpg"
        path = os.path.join(self._dest_folder, name)
        cv2.imwrite(path, self._last_frame)
        self._burst_count += 1

        self.progress.setValue(self._burst_count)
        self.label_progress.setText(f"{self._burst_count} / {self._burst_total}")
        self.label_last.setText(name)

        try:
            n = int(self.label_total.text())
        except ValueError:
            n = 0
        self.label_total.setText(str(n + 1))

        if self._burst_count >= self._burst_total:
            self._stop_burst()
            self.status_message.emit(
                f"✅  Ráfaga completa: {self._burst_total} fotos → {self._dest_folder}")

    def _stop_burst(self):
        self._burst_timer.stop()
        self.btn_burst.setEnabled(self._last_frame is not None)
        self.btn_stop.setEnabled(False)


# ─── Estilos ─────────────────────────────────────────────────────────────
GROUP_STYLE = """
QGroupBox {
    font-weight:bold; font-size:12px; color:#c9d1d9;
    border:1px solid #30363d; border-radius:8px;
    margin-top:8px; padding-top:6px;
}
QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 4px; }
"""
BTN_BURST = """
QPushButton {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #00b890, stop:1 #00d4aa);
    color:#000; font-weight:bold; border-radius:6px; font-size:14px;
}
QPushButton:hover   { background:#00ffcc; }
QPushButton:pressed { background:#009977; }
QPushButton:disabled{ background:#1c2128; color:#484f58; border:1px solid #30363d; }
"""
BTN_STOP = """
QPushButton { background:#7f1d1d; color:#fff; font-weight:bold; border-radius:5px; }
QPushButton:hover { background:#ef4444; }
QPushButton:disabled { background:#1c2128; color:#484f58; }
"""