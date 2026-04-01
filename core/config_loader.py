"""
core/config_loader.py
===============================
Maneja la lectura/escritura del pipeline_config.json
Calcula la ruta absoluta automáticamente para evitar errores.
"""

import json
import os
from pathlib import Path

# Calcula la ruta absoluta a la raíz del proyecto para encontrar el JSON siempre
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, "pipeline_config.json")


class CaptureConfig:
    """Lee y escribe el bloque 'capture' del pipeline_config.json."""

    def __init__(self, path: str = CONFIG_FILE):
        self._path = Path(path)
        self._data = {}
        self.load()

    def load(self):
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as f:
                full = json.load(f)
            self._data = full.get("capture", {})
        else:
            self._data = self._defaults()

    def save(self):
        full = {}
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as f:
                full = json.load(f)
        full["capture"] = self._data
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(full, f, indent=2, ensure_ascii=False)

    def _defaults(self) -> dict:
        return {
            "output_folder": str(Path.home() / "datasets"),
            "current_lote":  "lote_01",
            "interval_ms":   600,
            "burst_count":   80,
            "image_width":   640,
            "image_height":  640,
            "auto_rename":   True,
            "classes": [],
            "sizes": {
                "bottle": ["255ml", "355ml", "500ml", "600ml", "1L"],
                "can":    ["baja", "mediana", "alta"]
            }
        }

    # ── propiedades con getter/setter ─────────────────────────────────────────

    @property
    def output_folder(self) -> str:
        return self._data.get("output_folder", "")

    @output_folder.setter
    def output_folder(self, v: str):
        self._data["output_folder"] = v

    @property
    def current_lote(self) -> str:
        return self._data.get("current_lote", "lote_01")

    @current_lote.setter
    def current_lote(self, v: str):
        self._data["current_lote"] = v

    @property
    def interval_ms(self) -> int:
        return int(self._data.get("interval_ms", 600))

    @interval_ms.setter
    def interval_ms(self, v: int):
        self._data["interval_ms"] = v

    @property
    def burst_count(self) -> int:
        return int(self._data.get("burst_count", 80))

    @burst_count.setter
    def burst_count(self, v: int):
        self._data["burst_count"] = v

    @property
    def classes(self) -> list[str]:
        return self._data.get("classes", [])

    def add_class(self, name: str):
        if name and name not in self._data["classes"]:
            self._data["classes"].append(name)

    def remove_class(self, name: str):
        self._data["classes"] = [c for c in self._data["classes"] if c != name]

    @property
    def sizes_bottle(self) -> list[str]:
        return self._data.get("sizes", {}).get("bottle", [])

    @property
    def sizes_can(self) -> list[str]:
        return self._data.get("sizes", {}).get("can", [])

    # ── helper: genera lista de clases automática ─────────────────────────────

    def generate_classes_from_sizes(
        self,
        include_cap: bool = True,
        include_no_cap: bool = True
    ) -> list[str]:
        """
        Genera todas las combinaciones dinámicamente basadas en el JSON:
            botella_1L_con_tapa, botella_1L_sin_tapa, ...
            lata_alta, lata_baja, ...
            ninguno
        """
        classes = []
        for size in self.sizes_bottle:
            if include_cap:
                classes.append(f"botella_{size}_con_tapa")
            if include_no_cap:
                classes.append(f"botella_{size}_sin_tapa")
        for size in self.sizes_can:
            classes.append(f"lata_{size}")
        classes.append("ninguno")
        return classes

    def __repr__(self):
        return (
            f"CaptureConfig(lote={self.current_lote!r}, "
            f"interval={self.interval_ms}ms, burst={self.burst_count}, "
            f"classes={len(self.classes)})"
        )