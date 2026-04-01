"""
Widgets compartidos entre tabs.
"""
import cv2
import numpy as np
from PySide6.QtWidgets import QLabel, QWidget, QSizePolicy
from PySide6.QtCore    import Qt
from PySide6.QtGui     import QImage, QPixmap, QPainter, QColor, QBrush, QPen


# ─────────────────────────────────────────────────────────────
def frame_to_pixmap(frame: np.ndarray) -> QPixmap:
    """Convierte frame BGR de OpenCV a QPixmap."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    img = QImage(rgb.data.tobytes(), w, h, ch * w, QImage.Format_RGB888)
    return QPixmap.fromImage(img)


# ─────────────────────────────────────────────────────────────
class VideoLabel(QLabel):
    """QLabel que muestra frames de video manteniendo aspect ratio."""

    def __init__(self, placeholder: str = "📷  Sin señal de cámara"):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setText(placeholder)
        self._pixmap_raw: QPixmap | None = None
        self.setStyleSheet("""
            QLabel {
                background-color: #0d1117;
                color: #555;
                border: 2px solid #21262d;
                border-radius: 6px;
                font-size: 15px;
                font-family: 'Consolas', monospace;
            }
        """)

    def display_frame(self, frame: np.ndarray):
        self._pixmap_raw = frame_to_pixmap(frame)
        self._refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self):
        if self._pixmap_raw:
            scaled = self._pixmap_raw.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.setPixmap(scaled)

    def clear_frame(self):
        self._pixmap_raw = None
        self.clear()
        self.setText("📷  Sin señal de cámara")


# ─────────────────────────────────────────────────────────────
class StatusLED(QWidget):
    """LED indicador de estado (verde / rojo / gris)."""

    def __init__(self, size: int = 14):
        super().__init__()
        self._color  = QColor("#444")
        self._radius = size // 2
        self.setFixedSize(size, size)

    def set_ok(self):
        self._color = QColor("#00d4aa")
        self.update()

    def set_error(self):
        self._color = QColor("#ff4757")
        self.update()

    def set_idle(self):
        self._color = QColor("#444")
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(self._color.darker(150), 1))
        painter.setBrush(QBrush(self._color))
        r = self._radius
        painter.drawEllipse(1, 1, self.width() - 2, self.height() - 2)
        # Brillo
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 60)))
        painter.drawEllipse(3, 2, r - 2, r - 3)
