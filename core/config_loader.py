"""
PARCHE para ui/capture_tab.py
===============================
Muestra cómo leer las variables de captura desde pipeline_config.json
en lugar de tenerlas hardcodeadas.

Busca en tu capture_tab.py los valores fijos de intervalo, cantidad de fotos,
clases, etc., y reemplázalos con este loader.

1. Importa al inicio de capture_tab.py:
   from core.config_loader import CaptureConfig

2. En __init__ de CaptureTab:
   self._cfg = CaptureConfig()
   self._apply_config()

3. Al guardar cambios en UI, llama:
   self._cfg.save()
"""

import json
from pathlib import Path


CONFIG_FILE = "pipeline_config.json"


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
            "classes": [
                "botella_1L_con_tapa",
                "botella_600ml_con_tapa",
                "lata_355ml",
                "ninguno"
            ],
            "sizes": {
                "bottle": ["255ml", "355ml", "600ml", "1L"],
                "can":    ["255ml", "600ml"]
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
        Genera todas las combinaciones:
            botella_1L_con_tapa, botella_1L_sin_tapa, ...
            lata_355ml, lata_600ml, ...
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
