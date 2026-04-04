"""
WiFiManager — cliente TCP para ESP32 con WiFi.
Expone las mismas señales y métodos que SerialManager para
intercambio transparente vía ConnectionManager.

Puerto TCP por defecto: 8888
El ESP32 usa el mismo protocolo de texto que Serial (comandos + '\\n').
"""
import socket
from typing import Optional
from PySide6.QtCore import QObject, Signal, QThread


# ─────────────────────────────────────────────────────────────────────────
class _TCPReader(QThread):
    """Hilo de lectura no bloqueante sobre un socket TCP."""

    data_received   = Signal(str)
    us_data         = Signal(int, int)   # US1 cm, US2 cm
    event_received  = Signal(str)        # OBJ_AT_CAM, OBJ_ENTRY, TIMEOUT…
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
                    # El servidor cerró la conexión
                    if self._running:
                        self.connection_lost.emit()
                    break

                buf += chunk
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue

                    # Parsear US data (no saturar el log UI)
                    if line.startswith("US:"):
                        parts = line.split(":")
                        if len(parts) == 3:
                            try:
                                self.us_data.emit(int(parts[1]), int(parts[2]))
                            except ValueError:
                                pass
                        continue

                    if line.startswith("EVENT:"):
                        self.event_received.emit(line[6:])

                    self.data_received.emit(line)

            except OSError:
                if self._running:
                    self.connection_lost.emit()
                break

    def stop(self):
        self._running = False
        # Cerrar socket para desbloquear recv()
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        self.wait(1500)


# ─────────────────────────────────────────────────────────────────────────
class WiFiManager(QObject):
    """
    Gestor de conexión TCP al ESP32 vía WiFi (red local).

    Uso básico:
        mgr = WiFiManager()
        mgr.connect("192.168.1.100", 8888)
        mgr.belt_start()
        mgr.disconnect()
    """

    status_changed = Signal(str)          # mensaje de estado
    data_received  = Signal(str)          # línea recibida (filtrada, sin US)
    us_data        = Signal(int, int)     # US1 cm, US2 cm
    event_received = Signal(str)          # eventos del firmware
    connected      = Signal(bool)         # True / False

    DEFAULT_PORT = 8888

    def __init__(self):
        super().__init__()
        self._sock:   Optional[socket.socket] = None
        self._reader: Optional[_TCPReader]    = None

    # ── Conexión ─────────────────────────────────────────────────────────
    def connect(self, host: str, port: int = DEFAULT_PORT) -> bool:
        host = host.strip()
        if not host:
            self.status_changed.emit("❌ WiFi: IP vacía")
            self.connected.emit(False)
            return False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0)          # timeout solo en connect()
            s.connect((host, port))
            s.settimeout(None)         # bloqueante para el reader

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
            msg = f"❌ WiFi: timeout al conectar  {host}:{port}"
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
        """Llamado desde _TCPReader cuando el servidor cierra la conexión."""
        self._sock   = None
        self._reader = None
        self.status_changed.emit("⚠️ Conexión WiFi perdida")
        self.connected.emit(False)

    # ── Envío raw ────────────────────────────────────────────────────────
    def send(self, command: str) -> bool:
        if self._sock:
            try:
                self._sock.sendall(f"{command}\n".encode("utf-8"))
                return True
            except Exception as e:
                self.status_changed.emit(f"⚠️ WiFi tx: {e}")
                self._on_lost()
        return False

    @property
    def is_connected(self) -> bool:
        return self._sock is not None

    # ── API de alto nivel (espejo de SerialManager) ───────────────────────
    def belt_start(self):               self.send("BELT:START")
    def belt_stop(self):                self.send("BELT:STOP")
    def belt_speed(self, v: int):       self.send(f"BELT:SPEED:{v}")

    def sort(self, cls_id: int):        self.send(f"SORT:{cls_id}")
    def sort_home(self):                self.send("HOME")
    def set_sort_pos(self, cls: int, steps: int):
        self.send(f"SORT_POS:{cls}:{steps}")

    def servo1_open(self):              self.send("SERVO1:OPEN")
    def servo1_close(self):             self.send("SERVO1:CLOSE")
    def servo2_open(self):              self.send("SERVO2:OPEN")
    def servo2_close(self):             self.send("SERVO2:CLOSE")

    def emergency_stop(self):           self.send("E_STOP")
    def reset(self):                    self.send("RESET")
    def request_status(self):           self.send("STATUS")
