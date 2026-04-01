"""
CameraThread — captura frames en un hilo separado.

Detección de nombres de cámara (Windows):
  1. Intenta pygrabber (pip install pygrabber) — DirectShow, sin ruido
  2. Fallback: PowerShell Get-PnpDevice
  3. Fallback final: "Cámara N"

Fix Windows: usa CAP_DSHOW para evitar backend obsensor (Intel RealSense).
"""
import sys
import os
import json
import subprocess
import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal

# Backend por plataforma
if sys.platform == "win32":
    _BACKEND = cv2.CAP_DSHOW
elif sys.platform.startswith("linux"):
    _BACKEND = cv2.CAP_V4L2
else:
    _BACKEND = cv2.CAP_ANY


def _get_camera_names_windows(max_devices: int = 8) -> dict[int, str]:
    """Devuelve {índice: nombre} para cámaras Windows."""
    names: dict[int, str] = {}

    # ── Intento 1: pygrabber (DirectShow nativo) ──────────────────────
    try:
        from pygrabber.dshow_graph import FilterGraph  # type: ignore
        devices = FilterGraph().get_input_devices()
        for i, name in enumerate(devices):
            names[i] = name
        if names:
            return names
    except Exception:
        pass

    # ── Intento 2: PowerShell PnP (sin deps extra) ────────────────────
    try:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-PnpDevice -Class Camera -Status OK "
            "| Select-Object -ExpandProperty FriendlyName "
            "| ConvertTo-Json -Compress"
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=4
        )
        raw = result.stdout.strip()
        if raw:
            data = json.loads(raw)
            if isinstance(data, str):
                data = [data]
            for i, name in enumerate(data):
                names[i] = name
    except Exception:
        pass

    return names


def get_camera_names(max_test: int = 6) -> list[tuple[int, str]]:
    """
    Retorna [(índice, nombre)] de todas las cámaras disponibles.
    Suprime stderr de OpenCV durante el escaneo.
    """
    # Silenciar stderr al nivel OS (evita spam de obsensor en Windows)
    if sys.platform == "win32":
        _null = open(os.devnull, "w")
        _old  = os.dup(2)
        os.dup2(_null.fileno(), 2)

    # Obtener nombres por plataforma
    name_map: dict[int, str] = {}
    if sys.platform == "win32":
        name_map = _get_camera_names_windows(max_test)

    found: list[tuple[int, str]] = []
    for i in range(max_test):
        cap = cv2.VideoCapture(i, _BACKEND)
        if cap.isOpened():
            name = name_map.get(i, f"Cámara {i}")
            found.append((i, name))
            cap.release()

    if sys.platform == "win32":
        os.dup2(_old, 2)
        os.close(_old)
        _null.close()

    return found


# ─────────────────────────────────────────────────────────────────────────
class CameraThread(QThread):
    frame_ready = Signal(object)   # np.ndarray BGR
    error       = Signal(str)
    started_ok  = Signal(int)      # índice de cámara

    def __init__(self):
        super().__init__()
        self.camera_index = 0
        self._running     = False
        self._width       = 1280
        self._height      = 720

    def set_camera(self, index: int):
        self.camera_index = index

    def set_resolution(self, w: int, h: int):
        self._width, self._height = w, h

    def run(self):
        self._running = True

        if sys.platform == "win32":
            _null = open(os.devnull, "w")
            _old  = os.dup(2)
            os.dup2(_null.fileno(), 2)

        cap = cv2.VideoCapture(self.camera_index, _BACKEND)

        if sys.platform == "win32":
            os.dup2(_old, 2)
            os.close(_old)
            _null.close()

        if not cap.isOpened():
            self.error.emit(f"No se pudo abrir cámara {self.camera_index}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self._width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        cap.set(cv2.CAP_PROP_FPS, 30)
        self.started_ok.emit(self.camera_index)

        while self._running:
            ret, frame = cap.read()
            if ret:
                self.frame_ready.emit(frame)
            else:
                self.msleep(10)
            self.msleep(5)

        cap.release()

    def stop(self):
        self._running = False
        self.wait(3000)

    # Alias para compatibilidad con config_tab
    @staticmethod
    def list_cameras(max_test: int = 6) -> list[int]:
        return [idx for idx, _ in get_camera_names(max_test)]