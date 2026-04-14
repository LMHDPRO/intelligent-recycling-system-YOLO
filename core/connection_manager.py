"""
core/connection_manager.py
===========================
Fachada que unifica SerialManager y WiFiManager en una sola interfaz.

La UI solo habla con ConnectionManager — no necesita saber si el ESP32
está conectado por USB o por red WiFi. Basta con llamar a:

    cm = ConnectionManager()
    cm.connect_serial("COM3", 115200)   # o
    cm.connect_wifi("192.168.1.100")

    cm.belt_start()          # funciona igual en ambos modos
    cm.led_green()           # ídem
    cm.emergency_stop()      # ídem

    cm.disconnect()

Señales re-emitidas (idénticas a SerialManager / WiFiManager):
    status_changed(str)
    data_received(str)
    us_data(int, int)
    event_received(str)
    connected(bool)
    mode_changed(str)        # "serial" | "wifi" | "none"
"""
from PySide6.QtCore import QObject, Signal
from core.serial_manager import SerialManager
from core.wifi_manager   import WiFiManager


# ─────────────────────────────────────────────────────────────────────────
class ConnectionManager(QObject):
    """
    Fachada única para SerialManager y WiFiManager.

    Uso desde MainWindow:
        self._conn = ConnectionManager()
        # Pasar self._conn a DetectionTab y ConfigTab en lugar de
        # SerialManager directamente.
    """

    status_changed = Signal(str)
    data_received  = Signal(str)
    us_data        = Signal(int, int)
    event_received = Signal(str)
    connected      = Signal(bool)
    mode_changed   = Signal(str)    # "serial" | "wifi" | "none"

    def __init__(self):
        super().__init__()
        self._serial  = SerialManager()
        self._wifi    = WiFiManager()
        self._active  = None          # instancia activa (serial o wifi)
        self._mode    = "none"
        self._wire(self._serial)
        self._wire(self._wifi)

    # ── Conexión serial ───────────────────────────────────────────────────
    def connect_serial(self, port: str, baudrate: int) -> bool:
        self._disconnect_current()
        ok = self._serial.connect(port, baudrate)
        if ok:
            self._active = self._serial
            self._mode   = "serial"
            self.mode_changed.emit("serial")
        return ok

    # ── Conexión WiFi ─────────────────────────────────────────────────────
    def connect_wifi(self, host: str, port: int = WiFiManager.DEFAULT_PORT) -> bool:
        self._disconnect_current()
        ok = self._wifi.connect(host, port)
        if ok:
            self._active = self._wifi
            self._mode   = "wifi"
            self.mode_changed.emit("wifi")
        return ok

    # ── Desconexión ───────────────────────────────────────────────────────
    def disconnect(self):
        self._disconnect_current()

    def _disconnect_current(self):
        if self._active is not None:
            self._active.disconnect()
        self._active = None
        self._mode   = "none"
        self.mode_changed.emit("none")

    @property
    def is_connected(self) -> bool:
        return self._active is not None and self._active.is_connected

    @property
    def mode(self) -> str:
        """'serial' | 'wifi' | 'none'"""
        return self._mode

    # ── Envío raw ─────────────────────────────────────────────────────────
    def send(self, command: str) -> bool:
        if self._active:
            return self._active.send(command)
        return False

    def send_raw(self, command: str) -> bool:
        return self.send(command)

    # ── API completa (espejo de ambos managers) ───────────────────────────

    # Banda
    def belt_start(self):
        if self._active: self._active.belt_start()

    def belt_stop(self):
        if self._active: self._active.belt_stop()

    def belt_speed(self, v: int):
        if self._active: self._active.belt_speed(v)

    def belt_hold_on(self):
        if self._active: self._active.belt_hold_on()

    def belt_hold_off(self):
        if self._active: self._active.belt_hold_off()

    def belt_status(self):
        if self._active: self._active.belt_status()

    # Ultrasónicos
    def us_set_threshold(self, sensor: int, cm: int):
        if self._active: self._active.us_set_threshold(sensor, cm)

    def us_auto_on(self):
        if self._active: self._active.us_auto_on()

    def us_auto_off(self):
        if self._active: self._active.us_auto_off()

    def us_get(self):
        if self._active: self._active.us_get()

    # Sorting
    def sort(self, cls_id: int):
        if self._active: self._active.sort(cls_id)

    def sort_home(self):
        if self._active: self._active.sort_home()

    def set_sort_pos(self, cls: int, steps: int):
        if self._active: self._active.set_sort_pos(cls, steps)

    # Servos
    def servo1_open(self):   self._safe("servo1_open")
    def servo1_close(self):  self._safe("servo1_close")
    def servo2_open(self):   self._safe("servo2_open")
    def servo2_close(self):  self._safe("servo2_close")

    # LEDs
    def led_green(self):     self._safe("led_green")
    def led_red(self):       self._safe("led_red")
    def led_off(self):       self._safe("led_off")

    # Sistema
    def emergency_stop(self):
        if self._active: self._active.emergency_stop()

    def reset(self):
        if self._active: self._active.reset()

    def request_status(self):
        if self._active: self._active.request_status()

    # ── Acceso directo a los managers subyacentes ─────────────────────────
    @property
    def serial(self) -> SerialManager:
        return self._serial

    @property
    def wifi(self) -> WiFiManager:
        return self._wifi

    # ── Helpers privados ──────────────────────────────────────────────────
    def _safe(self, method: str):
        """Llama un método por nombre si hay conexión activa."""
        if self._active:
            getattr(self._active, method)()

    def _wire(self, mgr):
        """Conecta las señales de un manager a las de esta fachada."""
        mgr.status_changed.connect(self.status_changed)
        mgr.data_received.connect(self.data_received)
        mgr.us_data.connect(self.us_data)
        mgr.event_received.connect(self.event_received)
        mgr.connected.connect(self.connected)

    # ── Puertos disponibles (Serial) ──────────────────────────────────────
    @staticmethod
    def list_ports() -> list[str]:
        return SerialManager.list_ports()

    BAUDRATES = SerialManager.BAUDRATES