"""
Tab de Captura de Dataset v5.3
  • _SpinRow: widget propio con botones − / + visibles, reemplaza QSpinBox
  • Sin cambios de lógica
"""
import os
import cv2
import numpy as np
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
    QLabel, QComboBox, QPushButton, QLineEdit,
    QProgressBar, QFileDialog, QMessageBox,
    QSizePolicy, QFormLayout, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIntValidator

from ui.widgets import VideoLabel
from core.config_loader import CaptureConfig


# ── CSS base ──────────────────────────────────────────────────────────────
CLEAN_COMBO_CSS = """
QComboBox {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 4px;
    color: #c9d1d9;
    padding: 4px 8px;
    font-size: 13px;
}
QComboBox:focus { border-color: #58a6ff; }
QComboBox QAbstractItemView {
    background: #161b22;
    border: 1px solid #30363d;
    color: #c9d1d9;
    selection-background-color: #1f6feb;
}
"""


# ── Widget personalizado: reemplaza QSpinBox ──────────────────────────────
class _SpinRow(QWidget):
    """
    Campo numérico con botones  −  y  +  totalmente estilizados.
    Tiene la misma API mínima que QSpinBox: value() / setValue().
    """
    valueChanged = Signal(int)

    def __init__(self, minimum: int, maximum: int, value: int,
                 step: int = 1, suffix: str = "", parent=None):
        super().__init__(parent)
        self._min    = minimum
        self._max    = maximum
        self._step   = step
        self._suffix = suffix.strip()
        self._value  = max(minimum, min(maximum, value))

        self.setFixedHeight(32)

        # ── botón  − ─────────────────────────────────────────────────────
        self._btn_dec = QPushButton("−")
        self._btn_dec.setFixedSize(32, 32)
        self._btn_dec.setStyleSheet(_SPIN_BTN_CSS)
        self._btn_dec.clicked.connect(self._decrement)

        # ── campo de texto ────────────────────────────────────────────────
        self._edit = QLineEdit(str(self._value))
        self._edit.setAlignment(Qt.AlignCenter)
        self._edit.setValidator(QIntValidator(minimum, maximum))
        self._edit.setStyleSheet(_SPIN_EDIT_CSS)
        self._edit.setMinimumWidth(70)
        self._edit.editingFinished.connect(self._on_edit)

        # ── etiqueta de sufijo ────────────────────────────────────────────
        self._lbl_suffix = QLabel(self._suffix)
        self._lbl_suffix.setStyleSheet("color:#8b949e; font-size:12px;")
        self._lbl_suffix.setVisible(bool(self._suffix))

        # ── botón  + ─────────────────────────────────────────────────────
        self._btn_inc = QPushButton("+")
        self._btn_inc.setFixedSize(32, 32)
        self._btn_inc.setStyleSheet(_SPIN_BTN_CSS)
        self._btn_inc.clicked.connect(self._increment)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(self._btn_dec)
        lay.addWidget(self._edit, stretch=1)
        lay.addWidget(self._lbl_suffix)
        lay.addWidget(self._btn_inc)

    # ── API pública ───────────────────────────────────────────────────────
    def value(self) -> int:
        return self._value

    def setValue(self, v: int):
        self._value = max(self._min, min(self._max, v))
        self._edit.setText(str(self._value))

    # ── lógica interna ────────────────────────────────────────────────────
    def _increment(self):
        self.setValue(self._value + self._step)
        self.valueChanged.emit(self._value)

    def _decrement(self):
        self.setValue(self._value - self._step)
        self.valueChanged.emit(self._value)

    def _on_edit(self):
        try:
            self.setValue(int(self._edit.text()))
            self.valueChanged.emit(self._value)
        except ValueError:
            self._edit.setText(str(self._value))


# ── Estilos del SpinRow ───────────────────────────────────────────────────
_SPIN_BTN_CSS = """
QPushButton {
    background: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 4px;
    font-size: 18px;
    font-weight: bold;
    padding: 0;
}
QPushButton:hover   { background: #30363d; color: #ffffff; border-color: #8b949e; }
QPushButton:pressed { background: #0d1117; color: #58a6ff; }
"""

_SPIN_EDIT_CSS = """
QLineEdit {
    background: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 4px;
    font-size: 13px;
    padding: 2px 6px;
}
QLineEdit:focus { border-color: #58a6ff; }
"""


# ─────────────────────────────────────────────────────────────────────────
class _EditableCombo(QWidget):
    """ComboBox editable con botón  + Guardar  para persistir items."""
    changed = Signal(str)

    def __init__(self, items: list[str], placeholder: str = ""):
        super().__init__()
        self.setMinimumHeight(32)
        self._items = list(items) if items else []

        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.NoInsert)
        self.combo.lineEdit().setPlaceholderText(placeholder)
        self.combo.setMinimumHeight(28)
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo.setStyleSheet(CLEAN_COMBO_CSS)
        self._populate()

        self.btn_add = QPushButton("+ Guardar")
        self.btn_add.setToolTip("Añadir este nombre a la lista permanentemente")
        self.btn_add.setFixedHeight(28)
        self.btn_add.setMinimumWidth(82)
        self.btn_add.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                border: 1px solid #2ea043;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                padding: 0 8px;
            }
            QPushButton:hover   { background-color: #2ea043; }
            QPushButton:pressed { background-color: #196c2e; }
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(self.combo, stretch=1)
        lay.addWidget(self.btn_add)

        self.btn_add.clicked.connect(self._add_item)
        self.combo.currentTextChanged.connect(self.changed)

    def _populate(self):
        self.combo.clear()
        for item in self._items:
            self.combo.addItem(item)

    def _add_item(self):
        text = self.combo.currentText().strip().replace(" ", "_").lower()
        if text and text not in self._items:
            self._items.append(text)
            self.combo.addItem(text)
            self.combo.setCurrentText(text)

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

    _RIGHT_W = 340

    def __init__(self):
        super().__init__()
        self._last_frame: np.ndarray | None = None
        self._burst_count = 0
        self._burst_total = 0
        self._burst_timer = QTimer(self)
        self._burst_timer.timeout.connect(self._take_one)

        base_dir    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "pipeline_config.json")
        self._cfg         = CaptureConfig(config_path)
        self._save_folder = self._cfg.output_folder

        self._build_ui()
        self._connect_signals()

    # ──────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(12, 12, 12, 12)

        left = QVBoxLayout()
        self.video = VideoLabel("📷  Conecta la cámara en Configuración")
        self.video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.label_cam_info = QLabel("Sin cámara activa")
        self.label_cam_info.setAlignment(Qt.AlignCenter)
        self.label_cam_info.setStyleSheet(
            "color:#8b949e; font-size:12px; font-weight:bold;")

        left.addWidget(self.video)
        left.addWidget(self.label_cam_info)

        right_inner = QWidget()
        right_inner.setMinimumWidth(self._RIGHT_W)

        ri = QVBoxLayout(right_inner)
        ri.setSpacing(10)
        ri.setContentsMargins(4, 2, 4, 4)
        ri.addWidget(self._build_folder_group())
        ri.addWidget(self._build_capture_group())
        ri.addWidget(self._build_progress_group())
        ri.addWidget(self._build_stats_group())
        ri.addStretch()

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_scroll.setFixedWidth(self._RIGHT_W + 18)
        right_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #0d1117; width: 6px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #30363d; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0; }
        """)
        right_scroll.setWidget(right_inner)

        root.addLayout(left, stretch=1)
        root.addWidget(right_scroll, stretch=0)

    # ── Grupos ────────────────────────────────────────────────────────────
    def _build_folder_group(self) -> QGroupBox:
        g = QGroupBox("📁  Carpeta de salida")
        g.setStyleSheet(GROUP_STYLE)
        lay = QVBoxLayout(g)
        lay.setSpacing(8)

        self.label_folder = QLabel(self._save_folder)
        self.label_folder.setWordWrap(True)
        self.label_folder.setStyleSheet(
            "color:#58a6ff; font-size:11px; font-weight:bold;")

        self.btn_folder = QPushButton("📂  Seleccionar carpeta…")
        self.btn_folder.setFixedHeight(30)
        self.btn_folder.setStyleSheet(BTN_SECONDARY)

        lay.addWidget(self.label_folder)
        lay.addWidget(self.btn_folder)
        return g

    def _build_capture_group(self) -> QGroupBox:
        g = QGroupBox("⚙️  Configuración de captura")
        g.setStyleSheet(GROUP_STYLE)

        lay = QFormLayout(g)
        lay.setSpacing(10)
        lay.setContentsMargins(10, 14, 10, 10)
        lay.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        lotes = list(dict.fromkeys([self._cfg.current_lote, "lote_01", "lote_02"]))
        self.combo_batch = _EditableCombo(lotes, placeholder="nombre del lote…")
        self.combo_batch.combo.setCurrentText(self._cfg.current_lote)
        lay.addRow("Lote:", self.combo_batch)

        todas = list(dict.fromkeys(
            self._cfg.generate_classes_from_sizes() + self._cfg.classes
        ))
        self.combo_class = _EditableCombo(todas, placeholder="clase / etiqueta…")
        lay.addRow("Clase:", self.combo_class)

        self.label_dest_hint = QLabel("")
        self.label_dest_hint.setStyleSheet(
            "color:#8b949e; font-size:10px; font-style:italic;")
        self.label_dest_hint.setWordWrap(True)
        lay.addRow("", self.label_dest_hint)
        self._update_dest_hint()

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#30363d;"); lay.addRow(sep)

        # ── _SpinRow reemplaza QSpinBox ───────────────────────────────────
        self.spin_qty = _SpinRow(
            minimum=1, maximum=1000,
            value=self._cfg.burst_count,
            step=10, suffix="fotos"
        )
        lay.addRow("Cantidad:", self.spin_qty)

        self.spin_interval = _SpinRow(
            minimum=100, maximum=10000,
            value=self._cfg.interval_ms,
            step=100, suffix="ms"
        )
        lay.addRow("Intervalo:", self.spin_interval)

        self.btn_save_preset = QPushButton("💾  Guardar configuración")
        self.btn_save_preset.setFixedHeight(30)
        self.btn_save_preset.setStyleSheet(BTN_SECONDARY)
        lay.addRow("", self.btn_save_preset)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color:#30363d;"); lay.addRow(sep2)

        self.btn_burst = QPushButton("📸  TOMAR RÁFAGA")
        self.btn_burst.setFixedHeight(46)
        self.btn_burst.setEnabled(False)
        self.btn_burst.setStyleSheet(BTN_BURST)

        self.btn_stop = QPushButton("■  Detener")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setFixedHeight(32)
        self.btn_stop.setStyleSheet(BTN_STOP)

        lay.addRow("", self.btn_burst)
        lay.addRow("", self.btn_stop)
        return g

    def _build_progress_group(self) -> QGroupBox:
        g = QGroupBox("📊  Progreso")
        g.setStyleSheet(GROUP_STYLE)
        lay = QVBoxLayout(g)
        lay.setSpacing(6)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #30363d; border-radius: 4px;
                background: #0d1117; color: #ffffff;
                text-align: center; height: 20px; font-weight: bold;
            }
            QProgressBar::chunk { background: #2ea043; border-radius: 3px; }
        """)

        self.label_progress = QLabel("0 / 0")
        self.label_progress.setAlignment(Qt.AlignCenter)
        self.label_progress.setStyleSheet(
            "color:#ffffff; font-size:14px; font-family:Consolas; font-weight:bold;")

        lay.addWidget(self.progress)
        lay.addWidget(self.label_progress)
        return g

    def _build_stats_group(self) -> QGroupBox:
        g = QGroupBox("📈  Estadísticas")
        g.setStyleSheet(GROUP_STYLE)
        lay = QFormLayout(g)
        lay.setSpacing(6)
        lay.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.label_total = QLabel("0")
        self.label_total.setStyleSheet(
            "color:#2ea043; font-size:16px; font-weight:bold;")

        self.label_last = QLabel("—")
        self.label_last.setWordWrap(True)
        self.label_last.setStyleSheet(
            "color:#58a6ff; font-size:11px; font-weight:bold;")

        lay.addRow("Total guardadas:", self.label_total)
        lay.addRow("Último archivo:",  self.label_last)
        return g

    # ──────────────────────────────────────────────────────────────────────
    def _connect_signals(self):
        self.btn_folder.clicked.connect(self._select_folder)
        self.btn_burst.clicked.connect(self._start_burst)
        self.btn_stop.clicked.connect(self._stop_burst)
        self.btn_save_preset.clicked.connect(self._save_preset)
        self.combo_batch.changed.connect(self._update_dest_hint)
        self.combo_class.changed.connect(self._update_dest_hint)

    def receive_frame(self, frame: np.ndarray):
        self._last_frame = frame
        self.video.display_frame(frame)

    def on_camera_connected(self, idx: int):
        self.label_cam_info.setText(f"Cámara {idx} activa  ✅")
        self.label_cam_info.setStyleSheet(
            "color:#00d4aa; font-size:12px; font-weight:bold;")
        self.btn_burst.setEnabled(True)

    def on_camera_disconnected(self):
        self.label_cam_info.setText("Sin cámara activa")
        self.label_cam_info.setStyleSheet(
            "color:#ff4757; font-size:12px; font-weight:bold;")
        self.btn_burst.setEnabled(False)
        self.video.clear_frame()
        self._stop_burst()

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Carpeta de salida", self._save_folder)
        if folder:
            self._save_folder = folder
            self.label_folder.setText(folder)
            self._update_dest_hint()

    def _update_dest_hint(self, _=None):
        batch = self.combo_batch.current_text() or "lote"
        cls   = self.combo_class.current_text() or "clase"
        self.label_dest_hint.setText(os.path.join("…", batch, cls, "*.jpg"))

    def _save_preset(self):
        self.combo_batch._add_item()
        self.combo_class._add_item()
        self._cfg._data["classes"] = self.combo_class.get_items()
        self._cfg.current_lote     = self.combo_batch.current_text()
        self._cfg.output_folder    = self._save_folder
        self._cfg.burst_count      = self.spin_qty.value()
        self._cfg.interval_ms      = self.spin_interval.value()
        self._cfg.save()
        self.status_message.emit("✅  Configuración guardada en pipeline_config.json")

    def _start_burst(self):
        if self._last_frame is None:
            QMessageBox.warning(self, "Sin cámara", "Conecta la cámara primero.")
            return

        batch    = self.combo_batch.current_text() or "lote_01"
        cls      = self.combo_class.current_text() or "sin_clase"
        cls      = cls.replace(" ", "_").lower()
        total    = self.spin_qty.value()
        interval = self.spin_interval.value()

        dest = os.path.join(self._save_folder, batch, cls)
        os.makedirs(dest, exist_ok=True)

        self._dest_folder = dest
        self._burst_count = 0
        self._burst_total = total

        self.progress.setMaximum(total)
        self.progress.setValue(0)
        self.label_progress.setText(f"0 / {total}")

        self.btn_burst.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._burst_timer.start(interval)
        self.status_message.emit(
            f"📸  Ráfaga iniciada — {batch}/{cls}  ({total} fotos · {interval} ms)")

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


# ─── Estilos globales ─────────────────────────────────────────────────────
GROUP_STYLE = """
QGroupBox {
    font-weight: bold; font-size: 13px; color: #c9d1d9;
    border: 1px solid #30363d; border-radius: 6px;
    margin-top: 12px; padding-top: 8px;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
"""
BTN_SECONDARY = """
QPushButton {
    background: #21262d; color: #c9d1d9;
    border: 1px solid #30363d; border-radius: 5px; font-weight: bold;
}
QPushButton:hover   { background: #30363d; border-color: #8b949e; }
QPushButton:pressed { background: #161b22; }
"""
BTN_BURST = """
QPushButton {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #238636, stop:1 #2ea043);
    color: #ffffff; font-weight: bold; border-radius: 6px;
    font-size: 15px; border: 1px solid #3fb950;
}
QPushButton:hover    { background: #2ea043; }
QPushButton:pressed  { background: #196c2e; }
QPushButton:disabled { background: #1c2128; color: #484f58; border: 1px solid #30363d; }
"""
BTN_STOP = """
QPushButton {
    background: #da3633; color: #ffffff; font-weight: bold;
    border-radius: 5px; border: 1px solid #f85149; font-size: 13px;
}
QPushButton:hover    { background: #f85149; }
QPushButton:disabled { background: #1c2128; color: #484f58; border: 1px solid #30363d; }
"""