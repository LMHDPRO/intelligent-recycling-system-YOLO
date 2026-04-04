"""
ConnectionManager — abstracción sobre SerialManager y WiFiManager.

Expone exactamente las mismas señales y métodos que SerialManager,
enrutando internamente al manager activo (serial USB o WiFi TCP).

Uso en main.py — reemplaza la instancia de SerialManager:
    conn = ConnectionManager()
    # Pasar conn donde antes iba serial_manager

ConfigTab accede a conn.serial y conn.wifi directamente para
configurar cada modo por separado.
"""
from PySide6.QtCore import QObject, Signal

from core.serial_manager import SerialManager
from core.wifi_manager   import WiFiManager


# ─────────────────────────────────────────────────────────────────────────
class ConnectionManager(QObject):
    """
    Facade que hace transparente la elección Serial USB / WiFi TCP
    para el resto de la aplicación (DetectionTab, etc.).

    Señales idénticas a SerialManager — el resto del código no cambia.
    """

    status_changed = Signal(str)          # mensaje de estado
    data_received  = Signal(str)          # línea recibida (filtrada, sin US)
    us_data        = Signal(int, int)     # US1 cm, US2 cm
    event_received = Signal(str)          # eventos del firmware
    connected      = Signal(bool)         # True / False

    BAUDRATES = SerialManager.BAUDRATES   # compatibilidad con ConfigTab

    MODE_SERIAL = "serial"
    MODE_WIFI   = "wifi"

    def __init__(self):
        super().__init__()
        self.serial = SerialManager()
        self.wifi   = WiFiManager()
        self._mode  = self.MODE_SERIAL

        # ── Forwarding de Serial (solo cuando modo == serial) ─────────────
        self.serial.status_changed.connect(self._s_status)
        self.serial.data_received.connect(self._s_data)
        self.serial.us_data.connect(self._s_us)
        self.serial.event_received.connect(self._s_event)
        self.serial.connected.connect(self._s_connected)

        # ── Forwarding de WiFi (solo cuando modo == wifi) ─────────────────
        self.wifi.status_changed.connect(self._w_status)
        self.wifi.data_received.connect(self._w_data)
        self.wifi.us_data.connect(self._w_us)
        self.wifi.event_received.connect(self._w_event)
        self.wifi.connected.connect(self._w_connected)

    # ── Slots de forwarding condicional ───────────────────────────────────
    # Cada señal solo se propaga si el manager que la emitió es el activo.

    def _s_status(self, m: str):
        if self._mode == self.MODE_SERIAL:
            self.status_changed.emit(m)

    def _s_data(self, d: str):
        if self._mode == self.MODE_SERIAL:
            self.data_received.emit(d)

    def _s_us(self, a: int, b: int):
        if self._mode == self.MODE_SERIAL:
            self.us_data.emit(a, b)

    def _s_event(self, e: str):
        if self._mode == self.MODE_SERIAL:
            self.event_received.emit(e)

    def _s_connected(self, ok: bool):
        if self._mode == self.MODE_SERIAL:
            self.connected.emit(ok)

    def _w_status(self, m: str):
        if self._mode == self.MODE_WIFI:
            self.status_changed.emit(m)

    def _w_data(self, d: str):
        if self._mode == self.MODE_WIFI:
            self.data_received.emit(d)

    def _w_us(self, a: int, b: int):
        if self._mode == self.MODE_WIFI:
            self.us_data.emit(a, b)

    def _w_event(self, e: str):
        if self._mode == self.MODE_WIFI:
            self.event_received.emit(e)

    def _w_connected(self, ok: bool):
        if self._mode == self.MODE_WIFI:
            self.connected.emit(ok)

    # ── Gestión de modo ───────────────────────────────────────────────────
    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str):
        """
        Cambia el modo activo ('serial' o 'wifi').
        Desconecta el manager anterior si estaba conectado.
        """
        if mode not in (self.MODE_SERIAL, self.MODE_WIFI):
            return
        if mode == self._mode:
            return

        # Desconectar manager anterior ANTES de cambiar _mode,
        # para que los forwarding slots lo ignoren correctamente.
        old = self._active()
        self._mode = mode
        old.disconnect()

        label = "USB Serial" if mode == self.MODE_SERIAL else "WiFi TCP"
        self.status_changed.emit(f"🔄 Modo: {label}")
        self.connected.emit(False)

    # ── Manager activo ────────────────────────────────────────────────────
    def _active(self) -> SerialManager | WiFiManager:
        return self.serial if self._mode == self.MODE_SERIAL else self.wifi

    # ── Estado de conexión ────────────────────────────────────────────────
    @property
    def is_connected(self) -> bool:
        return self._active().is_connected

    # ── Envío raw ─────────────────────────────────────────────────────────
    def send(self, command: str) -> bool:
        return self._active().send(command)

    # ── API de alto nivel (delega al manager activo) ──────────────────────
    def belt_start(self):               self._active().belt_start()
    def belt_stop(self):                self._active().belt_stop()
    def belt_speed(self, v: int):       self._active().belt_speed(v)

    def sort(self, cls_id: int):        self._active().sort(cls_id)
    def sort_home(self):                self._active().sort_home()
    def set_sort_pos(self, cls: int, steps: int):
        self._active().set_sort_pos(cls, steps)

    def servo1_open(self):              self._active().servo1_open()
    def servo1_close(self):             self._active().servo1_close()
    def servo2_open(self):              self._active().servo2_open()
    def servo2_close(self):             self._active().servo2_close()

    def emergency_stop(self):           self._active().emergency_stop()
    def reset(self):                    self._active().reset()
    def request_status(self):           self._active().request_status()
