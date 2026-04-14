"""
WiFiManager — cliente TCP para ESP32 con WiFi.
Expone exactamente las mismas señales y métodos que SerialManager para
intercambio transparente vía ConnectionManager.

Puerto TCP por defecto: 8888
El ESP32 usa el mismo protocolo de texto que Serial (comandos + '\\n').

FIXES vs versión anterior:
  • US parser usa ',' como separador (igual que firmware y SerialManager)
    "US:45,32"  ← correcto   (antes usaba "US:45:32" ← incorrecto)
  • API completa: belt_hold_on/off, belt_status, us_set_threshold,
    us_auto_on/off, us_get, led_green, led_red, led_off
"""
import socket
from typing import Optional
from PySide6.QtCore import QObject, Signal, QThread


# ─────────────────────────────────────────────────────────────────────────
class _TCPReader(QThread):
    """Hilo de lectura no bloqueante sobre un socket TCP."""

    data_received   = Signal(str)
    us_data         = Signal(int, int)   # US1 cm, US2 cm
    event_received  = Signal(str)
    connection_lost = Signal()

    def __init__(self, sock: socket.socket):
        super().__init__()
        self._sock    = sock
        self._running = False

    def run(self):
        self._running = True
        buf = b""

        while self._running:
            try:
                chunk = self._sock.recv(256)
                if not chunk:
                    if self._running:
                        self.connection_lost.emit()
                    break

                buf += chunk
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue

                    # ── US:<d1>,<d2>  — MISMO formato que SerialManager ──
                    # FIX: el firmware envía "US:45,32" (coma), NO "US:45:32"
                    if line.startswith("US:") and "," in line:
                        payload = line[3:]          # "45,32"
                        parts   = payload.split(",")
                        if len(parts) == 2:
                            try:
                                self.us_data.emit(int(parts[0]), int(parts[1]))
                            except ValueError:
                                pass
                        continue   # no reenviar al log general

                    if line.startswith("EVENT:"):
                        self.event_received.emit(line[6:])

                    self.data_received.emit(line)

            except OSError:
                if self._running:
                    self.connection_lost.emit()
                break

    def stop(self):
        self._running = False
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        self.wait(1500)


# ─────────────────────────────────────────────────────────────────────────
class WiFiManager(QObject):
    """
    Gestor de conexión TCP al ESP32 vía WiFi (red local).

    Señales idénticas a SerialManager → intercambio transparente
    a través de ConnectionManager.
    """

    status_changed = Signal(str)
    data_received  = Signal(str)
    us_data        = Signal(int, int)
    event_received = Signal(str)
    connected      = Signal(bool)

    DEFAULT_PORT = 8888

    def __init__(self):
        super().__init__()
        self._sock:   Optional[socket.socket] = None
        self._reader: Optional[_TCPReader]    = None

    # ── Conexión / desconexión ────────────────────────────────────────────
    def connect(self, host: str, port: int = DEFAULT_PORT) -> bool:
        host = host.strip()
        if not host:
            self.status_changed.emit("❌ WiFi: IP vacía")
            self.connected.emit(False)
            return False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0)
            s.connect((host, port))
            s.settimeout(None)

            self._sock   = s
            self._reader = _TCPReader(self._sock)
            self._reader.data_received.connect(self.data_received)
            self._reader.us_data.connect(self.us_data)
            self._reader.event_received.connect(self.event_received)
            self._reader.connection_lost.connect(self._on_lost)
            self._reader.start()

            self.status_changed.emit(f"✅ WiFi  {host}:{port}")
            self.connected.emit(True)
            return True

        except ConnectionRefusedError:
            msg = f"❌ WiFi: conexión rechazada  {host}:{port}"
        except TimeoutError:
            msg = f"❌ WiFi: timeout  {host}:{port}"
        except Exception as e:
            msg = f"❌ WiFi: {e}"

        self._sock = None
        self.status_changed.emit(msg)
        self.connected.emit(False)
        return False

    def disconnect(self):
        if self._reader:
            self._reader.stop()
            self._reader = None
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        self.status_changed.emit("🔌 WiFi desconectado")
        self.connected.emit(False)

    def _on_lost(self):
        self._sock   = None
        self._reader = None
        self.status_changed.emit("⚠️ Conexión WiFi perdida")
        self.connected.emit(False)

    @property
    def is_connected(self) -> bool:
        return self._sock is not None

    # ── Envío base ────────────────────────────────────────────────────────
    def send(self, command: str) -> bool:
        if self._sock:
            try:
                self._sock.sendall(f"{command}\n".encode("utf-8"))
                return True
            except Exception as e:
                self.status_changed.emit(f"⚠️ WiFi tx: {e}")
                self._on_lost()
        return False

    def send_raw(self, command: str) -> bool:
        return self.send(command)

    # ── API idéntica a SerialManager ──────────────────────────────────────

    # Banda
    def belt_start(self):               self.send("BELT:START")
    def belt_stop(self):                self.send("BELT:STOP")
    def belt_speed(self, v: int):       self.send(f"BELT:SPEED:{v}")
    def belt_hold_on(self):             self.send("BELT:HOLD:ON")
    def belt_hold_off(self):            self.send("BELT:HOLD:OFF")
    def belt_status(self):              self.send("BELT:STATUS")

    # Ultrasónicos
    def us_set_threshold(self, sensor: int, cm: int):
        self.send(f"US:THRESH:{sensor}:{cm}")

    def us_auto_on(self):               self.send("US:AUTO:ON")
    def us_auto_off(self):              self.send("US:AUTO:OFF")
    def us_get(self):                   self.send("US:GET")

    # Sorting
    def sort(self, cls_id: int):        self.send(f"SORT:{cls_id}")
    def sort_home(self):                self.send("HOME")
    def set_sort_pos(self, cls: int, steps: int):
        self.send(f"SORT_POS:{cls}:{steps}")

    # Servos
    def servo1_open(self):              self.send("SERVO1:OPEN")
    def servo1_close(self):             self.send("SERVO1:CLOSE")
    def servo2_open(self):              self.send("SERVO2:OPEN")
    def servo2_close(self):             self.send("SERVO2:CLOSE")

    # LEDs de feedback (examen)
    def led_green(self):                self.send("LED:GREEN")
    def led_red(self):                  self.send("LED:RED")
    def led_off(self):                  self.send("LED:OFF")

    # Sistema
    def emergency_stop(self):           self.send("E_STOP")
    def reset(self):                    self.send("RESET")
    def request_status(self):           self.send("BELT:STATUS")