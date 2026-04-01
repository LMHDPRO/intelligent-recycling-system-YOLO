"""
SerialManager — gestiona la comunicación serial con ESP32.
Incluye SerialReader (hilo) para lectura no bloqueante.

Protocolo completo documentado en src/main.cpp del proyecto PlatformIO.
"""
import serial
import serial.tools.list_ports
from typing import Optional
from PySide6.QtCore import QObject, Signal, QThread


class _SerialReader(QThread):
    data_received  = Signal(str)
    us_data        = Signal(int, int)   # US1 cm, US2 cm
    event_received = Signal(str)        # OBJ_AT_CAM, OBJ_ENTRY, TIMEOUT…

    def __init__(self, ser: serial.Serial):
        super().__init__()
        self._ser     = ser
        self._running = False

    def run(self):
        self._running = True
        while self._running and self._ser and self._ser.is_open:
            try:
                if self._ser.in_waiting:
                    raw  = self._ser.readline()
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue

                    # Parsear US data en el hilo (evita saturar log UI)
                    if line.startswith("US:"):
                        parts = line.split(":")
                        if len(parts) == 3:
                            try:
                                d1 = int(parts[1])
                                d2 = int(parts[2])
                                self.us_data.emit(d1, d2)
                            except ValueError:
                                pass
                        continue   # no retransmitir US al log general

                    if line.startswith("EVENT:"):
                        self.event_received.emit(line[6:])

                    self.data_received.emit(line)
            except Exception:
                break
            self.msleep(10)

    def stop(self):
        self._running = False
        self.wait(1500)


# ─────────────────────────────────────────────────────────────────────────
class SerialManager(QObject):

    status_changed = Signal(str)         # mensaje de estado
    data_received  = Signal(str)         # línea recibida (filtrada, sin US)
    us_data        = Signal(int, int)    # US1 cm, US2 cm (cada ~100ms)
    event_received = Signal(str)         # OBJ_AT_CAM, OBJ_ENTRY, TIMEOUT…
    connected      = Signal(bool)        # True / False

    BAUDRATES = ["9600", "19200", "38400", "57600", "115200", "250000", "500000"]

    def __init__(self):
        super().__init__()
        self._ser:    Optional[serial.Serial] = None
        self._reader: Optional[_SerialReader] = None

    # ── Puertos ──────────────────────────────────────────────────────────
    @staticmethod
    def list_ports() -> list[str]:
        return [p.device for p in serial.tools.list_ports.comports()]

    # ── Conexión ─────────────────────────────────────────────────────────
    def connect(self, port: str, baudrate: int) -> bool:
        try:
            self._ser = serial.Serial(port, baudrate, timeout=1)
            self._reader = _SerialReader(self._ser)
            self._reader.data_received.connect(self.data_received)
            self._reader.us_data.connect(self.us_data)
            self._reader.event_received.connect(self.event_received)
            self._reader.start()
            self.status_changed.emit(f"✅ Conectado  {port}  @  {baudrate} baud")
            self.connected.emit(True)
            return True
        except Exception as e:
            self.status_changed.emit(f"❌ Error serial: {e}")
            self.connected.emit(False)
            return False

    def disconnect(self):
        if self._reader:
            self._reader.stop()
            self._reader = None
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._ser = None
        self.status_changed.emit("🔌 Desconectado")
        self.connected.emit(False)

    # ── Envío raw ────────────────────────────────────────────────────────
    def send(self, command: str) -> bool:
        if self._ser and self._ser.is_open:
            try:
                self._ser.write(f"{command}\n".encode("utf-8"))
                return True
            except Exception as e:
                self.status_changed.emit(f"⚠️ Error tx: {e}")
        return False

    @property
    def is_connected(self) -> bool:
        return self._ser is not None and self._ser.is_open

    # ── Banda — NEMA17 rotación constante ────────────────────────────────
    def belt_start(self):              self.send("BELT:START")
    def belt_stop(self):               self.send("BELT:STOP")
    def belt_speed(self, v: int):      self.send(f"BELT:SPEED:{v}")

    # ── Sorting — NEMA17 a pasos ──────────────────────────────────────────
    def sort(self, cls_id: int):       self.send(f"SORT:{cls_id}")
    def sort_home(self):               self.send("HOME")
    def set_sort_pos(self, cls: int, steps: int):
        self.send(f"SORT_POS:{cls}:{steps}")

    # ── Servos ────────────────────────────────────────────────────────────
    def servo1_open(self):             self.send("SERVO1:OPEN")
    def servo1_close(self):            self.send("SERVO1:CLOSE")
    def servo2_open(self):             self.send("SERVO2:OPEN")
    def servo2_close(self):            self.send("SERVO2:CLOSE")

    # ── Sistema ───────────────────────────────────────────────────────────
    def emergency_stop(self):          self.send("E_STOP")
    def reset(self):                   self.send("RESET")
    def request_status(self):          self.send("STATUS")