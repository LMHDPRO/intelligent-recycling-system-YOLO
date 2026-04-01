"""
ui/pipeline_panel.py
======================
Widget de panel de pipeline de modelos y su Diálogo flotante.
Layout en formato de árbol (Columnas) para mejor visualización.
"""

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QGroupBox, QFileDialog, QScrollArea, QFrame, QSizePolicy, QDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor


# Colores por estado del slot
_COLOR_LOADED   = "#27AE60"   # verde
_COLOR_EMPTY    = "#555555"   # gris
_COLOR_DISABLED = "#E67E22"   # naranja


class ModelSlot(QFrame):
    """
    Un slot de modelo: nombre, botón cargar, indicador, sliders conf/iou.
    """
    model_loaded   = Signal(str, str)   # (model_id, path)
    model_unloaded = Signal(str)        # model_id
    threshold_changed = Signal(str, float, float)  # (model_id, conf, iou)

    def __init__(self, model_cfg: dict, parent=None):
        super().__init__(parent)
        self._cfg = model_cfg
        self._mid = model_cfg["id"]
        self._loaded = False
        self._build()

    def _build(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background: #1e1e1e;
                border: 1px solid #333;
                border-radius: 6px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # ── Fila título ──────────────────────────────────────────────────────
        top = QHBoxLayout()
        num_label = QLabel(self._mid.split("_")[0])
        num_label.setStyleSheet("color:#888; font-size:10px;")
        name_label = QLabel(self._cfg["name"])
        name_label.setStyleSheet("color:#ddd; font-weight:bold; font-size:12px;")
        desc_label = QLabel(self._cfg["description"])
        desc_label.setStyleSheet("color:#777; font-size:10px;")

        top.addWidget(num_label)
        top.addWidget(name_label)
        top.addWidget(desc_label)
        top.addStretch()

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color:{_COLOR_EMPTY}; font-size:14px;")
        top.addWidget(self._status_dot)
        layout.addLayout(top)

        # ── Ruta del modelo ──────────────────────────────────────────────────
        self._path_label = QLabel("Sin modelo")
        self._path_label.setStyleSheet("color:#555; font-size:10px; font-style:italic;")
        self._path_label.setWordWrap(False)
        layout.addWidget(self._path_label)

        # ── Botones ──────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self._btn_load = QPushButton("📂 Cargar .pt")
        self._btn_load.setStyleSheet("""
            QPushButton {
                background:#2980B9; color:white; border:none;
                border-radius:4px; padding:4px 10px; font-size:11px;
            }
            QPushButton:hover { background:#3498DB; }
        """)
        self._btn_load.clicked.connect(self._on_load)

        self._btn_unload = QPushButton("✕")
        self._btn_unload.setStyleSheet("""
            QPushButton {
                background:#c0392b; color:white; border:none;
                border-radius:4px; padding:4px 8px; font-size:11px;
            }
            QPushButton:hover { background:#e74c3c; }
        """)
        self._btn_unload.setEnabled(False)
        self._btn_unload.clicked.connect(self._on_unload)

        btn_row.addWidget(self._btn_load)
        btn_row.addWidget(self._btn_unload)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # ── Sliders conf / IOU ───────────────────────────────────────────────
        thresholds = QHBoxLayout()

        conf_val = int(self._cfg.get("conf", 0.50) * 100)
        iou_val  = int(self._cfg.get("iou",  0.45) * 100)

        self._conf_lbl = QLabel(f"Conf: {conf_val/100:.2f}")
        self._conf_lbl.setStyleSheet("color:#aaa; font-size:10px;")
        self._conf_slider = QSlider(Qt.Orientation.Horizontal)
        self._conf_slider.setRange(10, 95)
        self._conf_slider.setValue(conf_val)
        self._conf_slider.setFixedWidth(80)
        self._conf_slider.valueChanged.connect(self._on_threshold_change)

        self._iou_lbl = QLabel(f"IOU: {iou_val/100:.2f}")
        self._iou_lbl.setStyleSheet("color:#aaa; font-size:10px;")
        self._iou_slider = QSlider(Qt.Orientation.Horizontal)
        self._iou_slider.setRange(10, 95)
        self._iou_slider.setValue(iou_val)
        self._iou_slider.setFixedWidth(80)
        self._iou_slider.valueChanged.connect(self._on_threshold_change)

        thresholds.addWidget(self._conf_lbl)
        thresholds.addWidget(self._conf_slider)
        thresholds.addSpacing(8)
        thresholds.addWidget(self._iou_lbl)
        thresholds.addWidget(self._iou_slider)
        thresholds.addStretch()
        layout.addLayout(thresholds)

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, f"Cargar modelo — {self._cfg['name']}",
            "", "PyTorch Model (*.pt)"
        )
        if path:
            short = Path(path).name
            self._path_label.setText(short)
            self._path_label.setStyleSheet("color:#27AE60; font-size:10px;")
            self._status_dot.setStyleSheet(f"color:{_COLOR_LOADED}; font-size:14px;")
            self._btn_unload.setEnabled(True)
            self._loaded = True
            self.model_loaded.emit(self._mid, path)

    def _on_unload(self):
        self._path_label.setText("Sin modelo")
        self._path_label.setStyleSheet("color:#555; font-size:10px; font-style:italic;")
        self._status_dot.setStyleSheet(f"color:{_COLOR_EMPTY}; font-size:14px;")
        self._btn_unload.setEnabled(False)
        self._loaded = False
        self.model_unloaded.emit(self._mid)

    def _on_threshold_change(self):
        conf = self._conf_slider.value() / 100
        iou  = self._iou_slider.value()  / 100
        self._conf_lbl.setText(f"Conf: {conf:.2f}")
        self._iou_lbl.setText(f"IOU:  {iou:.2f}")
        self.threshold_changed.emit(self._mid, conf, iou)

    def set_loaded(self, path: str):
        if path:
            self._path_label.setText(Path(path).name)
            self._path_label.setStyleSheet("color:#27AE60; font-size:10px;")
            self._status_dot.setStyleSheet(f"color:{_COLOR_LOADED}; font-size:14px;")
            self._btn_unload.setEnabled(True)
            self._loaded = True


# ── Panel completo ─────────────────────────────────────────────────────────────

class PipelinePanel(QGroupBox):
    """
    Panel lateral con todos los slots de modelos del pipeline.
    Organizado en columnas lógicas (Botellas vs Latas).
    """
    def __init__(self, worker, config_path: str = "pipeline_config.json", parent=None):
        super().__init__("⚙ Arquitectura del Pipeline de Modelos", parent)
        self._worker      = worker
        self._config_path = config_path
        self._slots: dict[str, ModelSlot] = {}
        self._build()
        self._restore_from_config()

    def _build(self):
        self.setStyleSheet("""
            QGroupBox {
                color: #ccc;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #444;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                top: -4px;
                padding: 0 4px;
            }
        """)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        main_vbox = QVBoxLayout(container)
        main_vbox.setSpacing(12)
        main_vbox.setContentsMargins(8, 8, 8, 8)

        # 1. Instanciar todos los slots disponibles
        models_cfg = self._worker.pipeline_cfg if self._worker else []
        created_slots = {}
        
        for m in models_cfg:
            slot = ModelSlot(m)
            slot.model_loaded.connect(self._on_model_loaded)
            slot.model_unloaded.connect(self._on_model_unloaded)
            slot.threshold_changed.connect(self._on_threshold)
            self._slots[m["id"]] = slot
            created_slots[m["id"]] = slot

        # ── ESTRUCTURACIÓN DEL ÁRBOL VISUAL ──

        # Nivel 1: Filtro de entrada (Ocupa todo el ancho)
        if "01_type" in created_slots:
            lbl_entrada = QLabel("↓ 1. CLASIFICACIÓN PRINCIPAL ↓")
            lbl_entrada.setStyleSheet("color: #8b949e; font-weight: bold; font-size: 11px;")
            lbl_entrada.setAlignment(Qt.AlignCenter)
            main_vbox.addWidget(lbl_entrada)
            main_vbox.addWidget(created_slots["01_type"])

        # Nivel 2: Bifurcación completa en 2 columnas (La forma de "Y")
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(16)

        # Columna Izquierda: Botellas
        left_col = QVBoxLayout()
        lbl_botellas = QLabel("🧴 RAMA: BOTELLAS")
        lbl_botellas.setStyleSheet("color: #ff4757; font-weight: bold; font-size: 12px;")
        lbl_botellas.setAlignment(Qt.AlignCenter)
        left_col.addWidget(lbl_botellas)

        # Agregamos los 4 modelos de botellas
        for mid in ["02_cap", "05_size_bottle", "03_brand_bottle", "07_condition_bottle"]:
            if mid in created_slots:
                left_col.addWidget(created_slots[mid])
        left_col.addStretch()

        # Columna Derecha: Latas
        right_col = QVBoxLayout()
        lbl_latas = QLabel("🥫 RAMA: LATAS")
        lbl_latas.setStyleSheet("color: #58a6ff; font-weight: bold; font-size: 12px;")
        lbl_latas.setAlignment(Qt.AlignCenter)
        right_col.addWidget(lbl_latas)

        # Agregamos los 3 modelos de latas
        for mid in ["06_size_can", "04_brand_can", "08_condition_can"]:
            if mid in created_slots:
                right_col.addWidget(created_slots[mid])
        right_col.addStretch()

        columns_layout.addLayout(left_col)
        columns_layout.addLayout(right_col)
        
        main_vbox.addSpacing(10)
        main_vbox.addLayout(columns_layout)

        main_vbox.addStretch()
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 16, 4, 4)
        outer.addWidget(scroll)

    def _restore_from_config(self):
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for m in cfg.get("pipeline", {}).get("models", []):
                slot = self._slots.get(m["id"])
                if slot and m.get("path") and Path(m["path"]).exists():
                    slot.set_loaded(m["path"])
        except Exception:
            pass

    def _on_model_loaded(self, model_id: str, path: str):
        if self._worker:
            ok = self._worker.load_model(model_id, path)
            if not ok:
                slot = self._slots.get(model_id)
                if slot:
                    slot._on_unload()

    def _on_model_unloaded(self, model_id: str):
        if self._worker:
            self._worker.unload_model(model_id)

    def _on_threshold(self, model_id: str, conf: float, iou: float):
        if self._worker:
            self._worker.set_threshold(model_id, conf, iou)


# ── Diálogo Flotante ───────────────────────────────────────────────────────────

class PipelineDialog(QDialog):
    """
    Ventana flotante rediseñada para acomodar el formato de dos columnas.
    """
    def __init__(self, worker, config_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Configuración del Pipeline de Modelos")
        
        # ── TAMAÑO AGRANDADO PARA ACOMODAR LAS DOS COLUMNAS ──
        self.setMinimumSize(850, 750) 
        
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.panel = PipelinePanel(worker, config_path, self)
        layout.addWidget(self.panel)

        self.btn_close = QPushButton("Cerrar y Aplicar")
        self.btn_close.setFixedHeight(36)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: #21262d; color: #c9d1d9; font-weight: bold; font-size: 13px;
                border: 1px solid #30363d; border-radius: 6px;
            }
            QPushButton:hover { background: #30363d; border-color: #8b949e; }
        """)
        self.btn_close.clicked.connect(self.accept)
        layout.addWidget(self.btn_close)