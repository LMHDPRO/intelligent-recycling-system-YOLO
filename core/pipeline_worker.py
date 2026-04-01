"""
core/pipeline_worker.py
========================
Reemplaza yolo_worker.py con un pipeline de N modelos YOLO secuenciales.
Cada modelo sólo corre si el anterior lo permitió (stop_on_unknown).
"""

import time
import json
import queue
import threading
from pathlib import Path

import cv2
from PySide6.QtCore import QThread, Signal
import numpy as np


# ── helpers ──────────────────────────────────────────────────────────────────

def _load_ultralytics():
    try:
        from ultralytics import YOLO
        return YOLO
    except ImportError:
        return None


# ── resultado de un paso del pipeline ────────────────────────────────────────

class StepResult:
    def __init__(self, model_id: str, label: str, conf: float, bbox=None):
        self.model_id = model_id   # "01_type", "02_cap", etc.
        self.label    = label      # clase ganadora
        self.conf     = conf       # confianza
        self.bbox     = bbox       # (x1,y1,x2,y2) o None si no hay detección


class PipelineResult:
    """Todo lo que sabe el pipeline tras procesar un frame."""
    def __init__(self):
        self.steps:     list[StepResult] = []
        self.annotated: np.ndarray | None = None
        self.price_mxn: float = 0.0
        self.stopped_at: str | None = None   # id del modelo que detuvo el pipeline

    # Acceso rápido por id
    def get(self, model_id: str) -> StepResult | None:
        return next((s for s in self.steps if s.model_id == model_id), None)

    @property
    def type(self)      -> str: return self.get("01_type").label     if self.get("01_type")      else "—"
    @property
    def cap(self)       -> str: return self.get("02_cap").label      if self.get("02_cap")       else "—"
    
    @property
    def brand(self)     -> str:
        b = self.get("03_brand_bottle") or self.get("04_brand_can")
        return b.label if b else "—"
        
    @property
    def size(self)      -> str:
        # LÓGICA ACTUALIZADA: Busca el tamaño en botellas o latas
        s = self.get("05_size_bottle") or self.get("06_size_can")
        return s.label if s else "—"
        
    @property
    def condition(self) -> str: 
        # ACTUALIZADO al id 07
        return self.get("07_condition").label if self.get("07_condition") else "—"


# ── worker principal ──────────────────────────────────────────────────────────

class PipelineWorker(QThread):
    """
    Señales:
      result_ready(PipelineResult)  — frame procesado
      error(str)                    — mensaje de error no fatal
    """
    result_ready = Signal(object)   # PipelineResult
    error        = Signal(str)

    def __init__(self, config_path: str = "pipeline_config.json", parent=None):
        super().__init__(parent)
        self._config_path = config_path
        self._config      = {}
        self._models      = {}      # model_id → YOLO instance
        self._q           = queue.Queue(maxsize=2)
        self._running     = False
        self._YOLO        = _load_ultralytics()
        self._load_config()

    # ── config ────────────────────────────────────────────────────────────────

    def _load_config(self):
        p = Path(self._config_path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        else:
            self._config = {}

    def reload_config(self):
        """Llamar desde UI al guardar cambios en el JSON."""
        self._load_config()

    @property
    def pipeline_cfg(self) -> list[dict]:
        return self._config.get("pipeline", {}).get("models", [])

    # ── gestión de modelos ────────────────────────────────────────────────────

    def load_model(self, model_id: str, path: str) -> bool:
        """Carga un .pt para un slot del pipeline. Retorna True si OK."""
        if not self._YOLO:
            self.error.emit("ultralytics no instalado — pip install ultralytics")
            return False
        if not Path(path).exists():
            self.error.emit(f"[{model_id}] Archivo no encontrado: {path}")
            return False
        try:
            self._models[model_id] = self._YOLO(path)
            # actualiza ruta en config
            for m in self.pipeline_cfg:
                if m["id"] == model_id:
                    m["path"]    = path
                    m["enabled"] = True
            self._save_config()
            return True
        except Exception as e:
            self.error.emit(f"[{model_id}] Error al cargar: {e}")
            return False

    def unload_model(self, model_id: str):
        self._models.pop(model_id, None)
        for m in self.pipeline_cfg:
            if m["id"] == model_id:
                m["enabled"] = False
        self._save_config()

    def set_threshold(self, model_id: str, conf: float, iou: float):
        for m in self.pipeline_cfg:
            if m["id"] == model_id:
                m["conf"] = conf
                m["iou"]  = iou
        self._save_config()

    def _save_config(self):
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # ── frames ────────────────────────────────────────────────────────────────

    def submit_frame(self, frame: np.ndarray):
        """Llama desde el hilo de cámara. Descarta si la cola está llena."""
        try:
            self._q.put_nowait(frame.copy())
        except queue.Full:
            pass

    # ── loop principal ────────────────────────────────────────────────────────

    def run(self):
        self._running = True
        while self._running:
            try:
                frame = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            result = self._run_pipeline(frame)
            self.result_ready.emit(result)

    def stop(self):
        self._running = False
        self.wait(3000)

    # ── inferencia ────────────────────────────────────────────────────────────

    def _run_pipeline(self, frame: np.ndarray) -> PipelineResult:
        result    = PipelineResult()
        annotated = frame.copy()
        current_type = None   # "botella" | "lata" | "desconocido"

        for model_cfg in self.pipeline_cfg:
            mid     = model_cfg["id"]
            enabled = model_cfg.get("enabled", False)

            if not enabled or mid not in self._models:
                continue

            # Filtro: ¿aplica para el tipo detectado?
            only_for = model_cfg.get("only_for_type")
            if only_for and current_type not in only_for:
                continue

            model = self._models[mid]
            conf  = model_cfg.get("conf", 0.50)
            iou   = model_cfg.get("iou",  0.45)

            try:
                preds = model.predict(
                    frame,
                    conf=conf,
                    iou=iou,
                    verbose=False
                )
            except Exception as e:
                self.error.emit(f"[{mid}] Error inferencia: {e}")
                continue

            step = self._parse_best(preds, mid)
            result.steps.append(step)

            # Anotar frame
            annotated = preds[0].plot() if preds else annotated

            # Propagar tipo para filtros posteriores
            if mid == "01_type":
                current_type = step.label
                cfg_stop = self._config.get("pipeline", {}).get("stop_on_unknown", True)
                if cfg_stop and current_type == "desconocido":
                    result.stopped_at = mid
                    break

        result.annotated = annotated
        result.price_mxn = self._calculate_price(result)
        return result

    def _parse_best(self, preds, model_id: str) -> StepResult:
        """Extrae la detección con mayor confianza."""
        if not preds or len(preds[0].boxes) == 0:
            return StepResult(model_id, "desconocido", 0.0)

        boxes = preds[0].boxes
        best_idx = int(boxes.conf.argmax())
        label    = preds[0].names[int(boxes.cls[best_idx])]
        conf     = float(boxes.conf[best_idx])
        xyxy     = boxes.xyxy[best_idx].tolist()
        return StepResult(model_id, label, conf, xyxy)

    # ── valorización ─────────────────────────────────────────────────────────

    def _calculate_price(self, result: PipelineResult) -> float:
        rules     = self._config.get("valuation", {}).get("rules", [])
        fallback  = self._config.get("valuation", {}).get("fallback_price", 0.05)

        t = result.type
        b = result.brand
        s = result.size
        c = result.condition

        best_match = None
        best_score = -1

        for rule in rules:
            rt = rule.get("type",      "*")
            rb = rule.get("brand",     "*")
            rs = rule.get("size",      "*")
            rc = rule.get("condition", "*")

            score = 0
            if rt != "*":
                if rt != t: continue
                score += 1
            if rb != "*":
                if rb != b: continue
                score += 1
            if rs != "*":
                if rs != s: continue
                score += 1
            if rc != "*":
                if rc != c: continue
                score += 1

            if score > best_score:
                best_score = score
                best_match = rule

        if best_match:
            return float(best_match.get("price_mxn", fallback))
        return fallback