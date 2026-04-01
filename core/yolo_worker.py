"""
YOLOWorker — infiere en un hilo separado.
- Recibe frames vía submit_frame() (drop si está ocupado).
- Emite result_ready con (frame_anotado, lista_de_detecciones).
- Funciona sin modelo cargado (pasa el frame sin anotar).
"""
import numpy as np
from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition


class YOLOWorker(QThread):
    result_ready = Signal(object, list)   # (np.ndarray, [{name, conf, class_id, xyxy}])
    model_loaded = Signal(bool, str)      # (ok, mensaje)

    def __init__(self):
        super().__init__()
        self.model       = None
        self.confidence  = 0.50
        self.iou         = 0.45
        self._running    = False
        self._frame      = None
        self._new_frame  = False
        self._mutex      = QMutex()
        self._cond       = QWaitCondition()

    # ─────────────────────────────────────────────────
    def load_model(self, model_path: str):
        """Carga el modelo YOLO (llamar desde hilo principal)."""
        try:
            from ultralytics import YOLO          # type: ignore
            self.model = YOLO(model_path)
            name = model_path.replace("\\", "/").split("/")[-1]
            self.model_loaded.emit(True, f"✅ {name}")
        except ImportError:
            self.model_loaded.emit(False, "❌ Instala: pip install ultralytics")
        except Exception as e:
            self.model_loaded.emit(False, f"❌ {e}")

    def unload_model(self):
        self.model = None
        self.model_loaded.emit(True, "ℹ️ Sin modelo (solo preview)")

    def set_confidence(self, val: float):
        self.confidence = val

    def set_iou(self, val: float):
        self.iou = val

    # ─────────────────────────────────────────────────
    def submit_frame(self, frame: np.ndarray):
        """Entrega un frame para inferencia; descarta el anterior si no procesó."""
        self._mutex.lock()
        self._frame     = frame.copy()
        self._new_frame = True
        self._cond.wakeOne()
        self._mutex.unlock()

    # ─────────────────────────────────────────────────
    def run(self):
        self._running = True
        while self._running:
            # Esperar frame
            self._mutex.lock()
            while not self._new_frame and self._running:
                self._cond.wait(self._mutex, 100)
            if not self._running:
                self._mutex.unlock()
                break
            frame = self._frame.copy()
            self._new_frame = False
            self._mutex.unlock()

            # Inferencia
            if self.model is not None:
                try:
                    results    = self.model.predict(
                        frame,
                        conf=self.confidence,
                        iou=self.iou,
                        verbose=False
                    )
                    annotated  = results[0].plot()
                    detections = [
                        {
                            "class_id": int(b.cls),
                            "name":     results[0].names[int(b.cls)],
                            "conf":     float(b.conf),
                            "xyxy":     b.xyxy[0].tolist(),
                        }
                        for b in results[0].boxes
                    ]
                    self.result_ready.emit(annotated, detections)
                except Exception:
                    self.result_ready.emit(frame, [])
            else:
                self.result_ready.emit(frame, [])

    def stop(self):
        self._mutex.lock()
        self._running = False
        self._cond.wakeAll()
        self._mutex.unlock()
        self.wait(4000)
