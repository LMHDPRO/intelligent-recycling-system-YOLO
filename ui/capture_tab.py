"""
Tab de Captura de Dataset v5.0:
  • UI Nativa Pura: 100% libre de hacks en flechas y sub-controles.
  • Botón "+" seguro y sin deformaciones.
  • Integración total con config_loader.
"""
import os
import cv2
import numpy as np
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
    QLabel, QComboBox, QPushButton, QSpinBox,
    QProgressBar, QFileDialog, QMessageBox,
    QSizePolicy, QFormLayout, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal

from ui.widgets import VideoLabel
from core.config_loader import CaptureConfig


# ── CSS NATIVO (Sin tocar pseudo-elementos ::) ──
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

CLEAN_SPIN_CSS = """
QSpinBox {
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 13px;
}
QSpinBox:focus { border-color: #58a6ff; }
"""


# ─────────────────────────────────────────────────────────────────────────
class _EditableCombo(QWidget):
    """ComboBox editable con un botón + limpio."""
    changed = Signal(str)

    def __init__(self, items: list[str], placeholder: str = ""):
        super().__init__()
        self._items = list(items) if items else []

        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.NoInsert)
        self.combo.lineEdit().setPlaceholderText(placeholder)
        self.combo.setMinimumHeight(28)
        self.combo.setStyleSheet(CLEAN_COMBO_CSS)

        self._populate()

        # Botón + limpio, sin fuentes raras que lo deformen
        self.btn_add = QPushButton("+")
        self.btn_add.setToolTip("Guardar clase en la lista permanentemente")
        self.btn_add.setFixedSize(28, 28)
        self.btn_add.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                border: 1px solid #2ea043;
                border-radius: 4px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover { background-color: #2ea043; }
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

    def __init__(self):
        super().__init__()
        self._last_frame: np.ndarray | None = None
        self._burst_count  = 0
        self._burst_total  = 0
        self._burst_timer  = QTimer(self)
        self._burst_timer.timeout.connect(self._take_one)
        
        # ── CEREBRO CENTRAL CON RUTA ABSOLUTA ──
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "pipeline_config.json")
        
        self._cfg = CaptureConfig(config_path)
        self._save_folder = self._cfg.output_folder

        self._build_ui()
        self._connect_signals()

    # ──────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(12, 12, 12, 12)

        left = QVBoxLayout()
        self.video = VideoLabel("📷  Conecta la cámara en Configuración")
        self.video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.label_cam_info = QLabel("Sin cámara activa")
        self.label_cam_info.setAlignment(Qt.AlignCenter)
        self.label_cam_info.setStyleSheet("color:#8b949e; font-size:12px; font-weight:bold;")
        left.addWidget(self.video)
        left.addWidget(self.label_cam_info)

        right = QVBoxLayout()
        right.setSpacing(12)
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
        lay.setSpacing(8)
        
        self.label_folder = QLabel(self._save_folder)
        self.label_folder.setWordWrap(True)
        self.label_folder.setStyleSheet("color:#58a6ff; font-size:11px; font-weight:bold;")
        
        self.btn_folder = QPushButton("📂  Seleccionar carpeta…")
        self.btn_folder.setFixedHeight(30)
        self.btn_folder.setStyleSheet("""
            QPushButton { background:#21262d; color:#c9d1d9; border:1px solid #30363d; border-radius:5px; font-weight:bold;}
            QPushButton:hover { background:#30363d; border-color:#8b949e; }
        """)
        
        lay.addWidget(self.label_folder)
        lay.addWidget(self.btn_folder)
        return g

    def _build_capture_group(self) -> QGroupBox:
        g = QGroupBox("⚙️  Configuración de captura")
        g.setStyleSheet(GROUP_STYLE)
        lay = QFormLayout(g)
        lay.setSpacing(12)
        lay.setLabelAlignment(Qt.AlignRight)

        self.combo_batch = _EditableCombo(
            [self._cfg.current_lote, "lote_02", "lote_03"],
            placeholder="nombre del lote…"
        )
        self.combo_batch.combo.setCurrentText(self._cfg.current_lote)
        lay.addRow("Lote:", self.combo_batch)

        clases_dinamicas = self._cfg.generate_classes_from_sizes()
        clases_guardadas = self._cfg.classes
        todas_las_clases = []
        for c in clases_dinamicas + clases_guardadas:
            if c not in todas_las_clases:
                todas_las_clases.append(c)

        self.combo_class = _EditableCombo(
            todas_las_clases,
            placeholder="clase / etiqueta…"
        )
        lay.addRow("Clase:", self.combo_class)

        self.label_dest_hint = QLabel("")
        self.label_dest_hint.setStyleSheet("color:#8b949e; font-size:10px; font-style:italic;")
        self.label_dest_hint.setWordWrap(True)
        lay.addRow("", self.label_dest_hint)

        self._update_dest_hint()

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#30363d;"); lay.addRow(sep)

        # ── SpinBoxes Nativos Limpios ──
        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 1000)
        self.spin_qty.setValue(self._cfg.burst_count)
        self.spin_qty.setSuffix("  fotos")
        self.spin_qty.setMinimumHeight(28)
        self.spin_qty.setStyleSheet(CLEAN_SPIN_CSS)
        lay.addRow("Cantidad:", self.spin_qty)

        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(100, 10000)
        self.spin_interval.setValue(self._cfg.interval_ms)
        self.spin_interval.setSuffix("  ms")
        self.spin_interval.setSingleStep(100)
        self.spin_interval.setMinimumHeight(28)
        self.spin_interval.setStyleSheet(CLEAN_SPIN_CSS)
        lay.addRow("Intervalo:", self.spin_interval)

        self.btn_save_preset = QPushButton("💾  Guardar configuración")
        self.btn_save_preset.setFixedHeight(30)
        self.btn_save_preset.setStyleSheet("""
            QPushButton { background:#21262d; color:#c9d1d9; border:1px solid #30363d; border-radius:5px; font-weight:bold;}
            QPushButton:hover { background:#30363d; border-color:#8b949e; }
        """)
        lay.addRow("", self.btn_save_preset)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color:#30363d;"); lay.addRow(sep2)

        self.btn_burst = QPushButton("📸  TOMAR RÁFAGA")
        self.btn_burst.setFixedHeight(46)
        self.btn_burst.setEnabled(False)
        self.btn_burst.setStyleSheet(BTN_BURST)

        self.btn_stop  = QPushButton("■  Detener")
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
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setStyleSheet("""
            QProgressBar { border:1px solid #30363d; border-radius:4px;
                           background:#0d1117; color:#ffffff; text-align:center; height:20px; font-weight:bold; }
            QProgressBar::chunk { background:#2ea043; border-radius:3px; }
        """)
        self.label_progress = QLabel("0 / 0")
        self.label_progress.setAlignment(Qt.AlignCenter)
        self.label_progress.setStyleSheet("color:#ffffff; font-size:14px; font-family:Consolas; font-weight:bold;")
        lay.addWidget(self.progress)
        lay.addWidget(self.label_progress)
        return g

    def _build_stats_group(self) -> QGroupBox:
        g = QGroupBox("📈  Estadísticas")
        g.setStyleSheet(GROUP_STYLE)
        lay = QFormLayout(g)
        lay.setSpacing(6)
        
        self.label_total = QLabel("0")
        self.label_total.setStyleSheet("color:#2ea043; font-size:16px; font-weight:bold;")
        
        self.label_last  = QLabel("—")
        self.label_last.setStyleSheet("color:#58a6ff; font-size:12px; font-weight:bold;")
        
        lay.addRow("Total guardadas:", self.label_total)
        lay.addRow("Último archivo:", self.label_last)
        return g

    # ──────────────────────────────────────────────────────────────────────
    def _connect_signals(self):
        self.btn_folder.clicked.connect(self._select_folder)
        self.btn_burst.clicked.connect(self._start_burst)
        self.btn_stop.clicked.connect(self._stop_burst)
        self.btn_save_preset.clicked.connect(self._save_preset)

        self.combo_batch.changed.connect(self._update_dest_hint)
        self.combo_class.changed.connect(self._update_dest_hint)

    # ── Slots públicos ────────────────────────────────────────────────────
    def receive_frame(self, frame: np.ndarray):
        self._last_frame = frame
        self.video.display_frame(frame)

    def on_camera_connected(self, idx: int):
        self.label_cam_info.setText(f"Cámara {idx} activa  ✅")
        self.label_cam_info.setStyleSheet("color:#00d4aa; font-size:12px; font-weight:bold;")
        self.btn_burst.setEnabled(True)

    def on_camera_disconnected(self):
        self.label_cam_info.setText("Sin cámara activa")
        self.label_cam_info.setStyleSheet("color:#ff4757; font-size:12px; font-weight:bold;")
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

    def _update_dest_hint(self, _=None):
        batch = self.combo_batch.current_text() or "lote"
        cls   = self.combo_class.current_text() or "clase"
        short = os.path.join("…", batch, cls, "*.jpg")
        self.label_dest_hint.setText(short)

    # ── Presets ───────────────────────────────────────────────────────────
    def _save_preset(self):
        # Asegurar auto-guardado visual antes de mandar al JSON
        self.combo_batch._add_item()
        self.combo_class._add_item()

        self._cfg._data["classes"] = self.combo_class.get_items()
        self._cfg.current_lote     = self.combo_batch.current_text()
        self._cfg.output_folder    = self._save_folder
        self._cfg.burst_count      = self.spin_qty.value()
        self._cfg.interval_ms      = self.spin_interval.value()
        self._cfg.save()
        self.status_message.emit("✅  Configuración guardada en pipeline_config.json")

    # ── Ráfaga ────────────────────────────────────────────────────────────
    def _start_burst(self):
        if self._last_frame is None:
            QMessageBox.warning(self, "Sin cámara", "Conecta la cámara primero.")
            return

        batch    = self.combo_batch.current_text() or "lote_01"
        cls      = self.combo_class.current_text() or "sin_clase"
        
        # Forzar formato
        cls = cls.replace(" ", "_").lower()
        
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
    font-weight:bold; font-size:13px; color:#c9d1d9;
    border:1px solid #30363d; border-radius:6px;
    margin-top:12px; padding-top:8px;
}
QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 4px; }
"""
BTN_BURST = """
QPushButton {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #238636, stop:1 #2ea043);
    color:#ffffff; font-weight:bold; border-radius:6px; font-size:15px; border: 1px solid #3fb950;
}
QPushButton:hover   { background:#2ea043; }
QPushButton:pressed { background:#196c2e; }
QPushButton:disabled{ background:#1c2128; color:#484f58; border:1px solid #30363d; }
"""
BTN_STOP = """
QPushButton { background:#da3633; color:#ffffff; font-weight:bold; border-radius:5px; border: 1px solid #f85149; font-size:13px; }
QPushButton:hover { background:#f85149; }
QPushButton:disabled { background:#1c2128; color:#484f58; border:1px solid #30363d; }
"""