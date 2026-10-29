# TV Remote Universal+ / LG iPhone
# Runs locally on iPhone inside Pyto (graphical interface) or a-Shell (terminal).
# Python 3.10+, standard library only. No cloud gateway or Windows PC required.
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
import ipaddress

PERMISSIONS = [
    "LAUNCH", "LAUNCH_WEBAPP", "APP_TO_APP", "CLOSE", "CONTROL_AUDIO",
    "CONTROL_DISPLAY", "CONTROL_INPUT_JOYSTICK", "CONTROL_INPUT_MEDIA_PLAYBACK",
    "CONTROL_INPUT_TV", "CONTROL_POWER", "CONTROL_TV_SCREEN",
    "READ_APP_STATUS", "READ_CURRENT_CHANNEL", "READ_INPUT_DEVICE_LIST",
    "READ_RUNNING_APPS", "READ_TV_CHANNEL_LIST", "READ_POWER_STATE",
    "READ_SETTINGS", "CONTROL_INPUT_TEXT", "CONTROL_MOUSE_AND_KEYBOARD",
    "READ_INSTALLED_APPS", "WRITE_NOTIFICATION_TOAST",
]
SETTINGS_FILE = Path.home() / "Documents" / "lg_remote_iphone.json"


def validate_ip(host):
    try:
        addr = ipaddress.ip_address(host.strip())
    except ValueError:
        raise ValueError("Introduce la IP del televisor, por ejemplo 192.168.1.45")
    if not (addr.is_private or addr.is_link_local):
        raise ValueError("Solo se permite conectar a una IP local privada")
    return str(addr)


class TVWebSocket:
    """Small RFC6455 synchronous WebSocket client; zero pip dependencies."""

    def __init__(self, url, timeout=8):
        parts = urlsplit(url)
        if parts.scheme not in ("ws", "wss"):
            raise ValueError("URL WebSocket no valida")
        self.host = parts.hostname
        self.port = parts.port or (443 if parts.scheme == "wss" else 80)
        self.path = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
        if not self.host:
            raise ValueError("Falta el host WebSocket")
        self.sock = socket.create_connection((self.host, self.port), timeout=timeout)
        try:
            if parts.scheme == "wss":
                # LG webOS commonly has a self-signed cert on the LOCAL TV.
                # Never use this socket for public Internet endpoints.
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                self.sock = ctx.wrap_socket(self.sock, server_hostname=self.host)
            self.sock.settimeout(timeout)
            key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
            request = (
                "GET " + self.path + " HTTP/1.1\r\n"
                "Host: " + self.host + ":" + str(self.port) + "\r\n"
                "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                "Sec-WebSocket-Version: 13\r\nSec-WebSocket-Key: " + key + "\r\n"
                "Origin: null\r\n\r\n"
            )
            self.sock.sendall(request.encode("ascii"))
            buf = b""
            while b"\r\n\r\n" not in buf:
                piece = self.sock.recv(4096)
                if not piece:
                    raise ConnectionError("La TV ha cerrado el enlace WebSocket")
                buf += piece
                if len(buf) > 32768:
                    raise ConnectionError("Cabeceras WebSocket demasiado largas")
            header, self.pending = buf.split(b"\r\n\r\n", 1)
            status = header.split(b"\r\n", 1)[0]
            if b" 101 " not in status:
                raise ConnectionError("La TV no acepta WebSocket: " + status.decode("utf-8", "replace"))
            fields = {}
            for line in header.split(b"\r\n")[1:]:
                if b":" in line:
                    k, v = line.split(b":", 1)
                    fields[k.strip().lower()] = v.strip()
            expected = base64.b64encode(hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
            ).digest())
            if fields.get(b"sec-websocket-accept") != expected:
                raise ConnectionError("La respuesta WebSocket no se ha validado")
        except Exception:
            self.sock.close()
            raise

    def _exact(self, n):
        out = bytearray()
        if self.pending:
            chunk = self.pending[:n]
            out.extend(chunk)
            self.pending = self.pending[n:]
        while len(out) < n:
            chunk = self.sock.recv(n - len(out))
            if not chunk:
                raise ConnectionError("La TV ha cerrado la conexion")
            out.extend(chunk)
        return bytes(out)

    def _frame(self, payload, opcode=1):
        payload = payload if isinstance(payload, bytes) else payload.encode("utf-8")
        head = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            head.append(0x80 | length)
        elif length < 65536:
            head.append(0x80 | 126)
            head.extend(struct.pack("!H", length))
        else:
            head.append(0x80 | 127)
            head.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        head.extend(mask)
        self.sock.sendall(bytes(head) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def send(self, text):
        self._frame(text, 1)

    def receive(self):
        fragments = []
        for _ in range(50):
            first, second = self._exact(2)
            opcode = first & 0x0F
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._exact(8))[0]
            if length > 2_000_000:
                raise ConnectionError("Mensaje WebSocket demasiado grande")
            mask = self._exact(4) if second & 0x80 else None
            payload = self._exact(length)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if opcode == 9:
                self._frame(payload, 10)
                continue
            if opcode == 10:
                continue
            if opcode == 8:
                raise ConnectionError("La TV ha cerrado el WebSocket")
            if opcode in (0, 1, 2):
                fragments.append(payload)
                if first & 0x80:
                    return b"".join(fragments).decode("utf-8", "replace")
        raise ConnectionError("Demasiados fragmentos WebSocket")

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


class LGController:
    def __init__(self):
        self.ip = None
        self.ws = None
        self.pointer = None
        self.counter = 0
        self.apps = []
        self.inputs = []
        self.cfg = {}
        try:
            self.cfg = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass

    def saved_ip(self):
        return self.cfg.get("ip", "")

    def close(self):
        if self.pointer:
            self.pointer.close()
        if self.ws:
            self.ws.close()
        self.pointer = None
        self.ws = None

    def connect(self, address, message=None):
        ip = validate_ip(address)
        self.close()
        self.ip = ip
        errors = []
        for scheme, port in (("wss", 3001), ("ws", 3000)):
            try:
                self.ws = TVWebSocket(f"{scheme}://{ip}:{port}/", timeout=7)
                break
            except (OSError, ValueError) as exc:
                errors.append(f"{port}: {exc}")
        if not self.ws:
            raise ConnectionError("No se puede contactar con LG. " + " | ".join(errors))
        self.ws.sock.settimeout(45)
        saved_key = self.cfg.get("keys", {}).get(ip)
        payload = {
            "pairingType": "PROMPT", "forcePairing": False,
            "manifest": {"manifestVersion": 1, "appVersion": "1.0",
                         "permissions": PERMISSIONS}
        }
        if saved_key:
            payload["client-key"] = saved_key
        self.ws.send(json.dumps({"type": "register", "id": "register_1", "payload": payload}))
        if message:
            message("Acepta el permiso en la pantalla del televisor...")
        try:
            for _ in range(24):
                response = json.loads(self.ws.receive())
                typ = response.get("type")
                if typ == "registered":
                    key = response.get("payload", {}).get("client-key")
                    if key:
                        self.cfg.setdefault("keys", {})[ip] = key
                        self.cfg["ip"] = ip
                        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
                        SETTINGS_FILE.write_text(json.dumps(self.cfg), encoding="utf-8")
                    self.ws.sock.settimeout(9)
                    return True
                if typ == "error":
                    raise ConnectionError(str(response.get("error") or response))
            raise TimeoutError("El televisor no ha confirmado el emparejamiento")
        except Exception:
            self.close()
            raise

    def call(self, uri, payload=None):
        if not self.ws:
            raise RuntimeError("Primero conecta con el televisor")
        self.counter += 1
        request_id = f"remote_{self.counter}"
        data = {"type": "request", "id": request_id, "uri": uri}
        if payload is not None:
            data["payload"] = payload
        self.ws.send(json.dumps(data, separators=(",", ":")))
        for _ in range(25):
            response = json.loads(self.ws.receive())
            if response.get("id") != request_id:
                continue
            if response.get("type") == "error" or response.get("payload", {}).get("returnValue") is False:
                raise RuntimeError(str(response.get("error") or response.get("payload")))
            return response.get("payload", {})
        raise TimeoutError("La TV no ha respondido al comando")

    def press(self, name):
        if not self.pointer:
            result = self.call("ssap://com.webos.service.networkinput/getPointerInputSocket")
            url = result.get("socketPath", "")
            parts = urlsplit(url)
            # Avoid sending commands/keys to a server returned outside the TV.
            if parts.hostname != self.ip or parts.scheme not in ("ws", "wss") or parts.port not in (3000, 3001):
                raise ConnectionError("Ruta de mando inesperada devuelta por la TV")
            self.pointer = TVWebSocket(url)
        self.pointer.send("type:button\nname:" + name + "\n\n")

    def volume(self, up=True):
        return self.call("ssap://audio/volumeUp" if up else "ssap://audio/volumeDown")

    def channel(self, up=True):
        return self.call("ssap://tv/channelUp" if up else "ssap://tv/channelDown")

    def mute(self):
        return self.press("MUTE")

    def power_off(self):
        return self.call("ssap://system/turnOff")

    def live_tv(self):
        return self.call("ssap://system.launcher/launch", {"id": "com.webos.app.livetv"})

    def picture_settings(self):
        return self.call("ssap://system.launcher/launch",
                         {"id": "com.palm.app.settings", "params": {"target": "picture"}})

    def list_apps(self):
        res = self.call("ssap://com.webos.applicationManager/listLaunchPoints")
        self.apps = sorted([
            (a.get("title") or a.get("id", "App"), a["id"])
            for a in res.get("launchPoints", []) if a.get("id") and a.get("visible", True)
        ], key=lambda x: x[0].lower())
        return self.apps

    def launch_app(self, app_id):
        return self.call("ssap://system.launcher/launch", {"id": app_id})

    def list_inputs(self):
        res = self.call("ssap://tv/getExternalInputList")
        self.inputs = [(a.get("label") or a.get("id", "HDMI"), a["id"])
                       for a in res.get("devices", []) if a.get("id")]
        return self.inputs

    def switch_input(self, input_id):
        return self.call("ssap://tv/switchInput", {"inputId": input_id})

    def write_text(self, text):
        if not text:
            return
        return self.call("ssap://com.webos.service.ime/insertText", {"text": text, "replace": 0})


controller = LGController()


def start_pyto():
    import pyto_ui as ui
    from mainthread import mainthread

    executor = ThreadPoolExecutor(max_workers=1)
    screen = ui.View()
    screen.title = "LG Remote+"
    screen.size = (390, 800)
    screen.background_color = ui.COLOR_SYSTEM_BACKGROUND

    label = ui.Label(text="Desconectado")
    label.frame = (18, 16, 350, 40)
    screen.add_subview(label)

    ip_field = ui.TextField()
    ip_field.frame = (18, 65, 225, 44)
    ip_field.text = controller.saved_ip()
    ip_field.placeholder = "IP del LG: 192.168.1.45"
    screen.add_subview(ip_field)

    status = ui.Label(text="LG webOS · Control por Wi-Fi local")
    status.frame = (18, 116, 354, 45)
    screen.add_subview(status)
    controls = ui.View()
    controls.frame = (10, 164, 370, 603)
    screen.add_subview(controls)

    @mainthread
    def tell(msg):
        status.text = str(msg)[:85]

    def dispatch(fn, success=None):
        def run():
            try:
                res = fn()
                if success is not None:
                    tell(success)
                return res
            except Exception as exc:
                tell("Error: " + str(exc))
                return None
        return executor.submit(run)

    def add_button(target, title, x, y, width, height, func):
        button = ui.Button(title=title)
        button.frame = (x, y, width, height)
        button.action = lambda sender: dispatch(func)
        target.add_subview(button)
        return button

    @mainthread
    def show_page(name="remote", offset=0):
        for sub in list(controls.subviews):
            controls.remove_subview(sub)
        if name == "remote":
            add_button(controls, "Apagar", 6, 0, 100, 46, controller.power_off)
            add_button(controls, "Inicio", 130, 0, 100, 46, lambda: controller.press("HOME"))
            add_button(controls, "Atras", 256, 0, 100, 46, lambda: controller.press("BACK"))

            add_button(controls, "▲", 136, 65, 100, 68, lambda: controller.press("UP"))
            add_button(controls, "◀", 26, 144, 100, 68, lambda: controller.press("LEFT"))
            add_button(controls, "OK", 136, 144, 100, 68, lambda: controller.press("ENTER"))
            add_button(controls, "▶", 246, 144, 100, 68, lambda: controller.press("RIGHT"))
            add_button(controls, "▼", 136, 225, 100, 68, lambda: controller.press("DOWN"))

            add_button(controls, "Vol +", 10, 315, 102, 65, lambda: controller.volume(True))
            add_button(controls, "Silencio", 134, 315, 104, 65, controller.mute)
            add_button(controls, "Canal +", 258, 315, 102, 65, lambda: controller.channel(True))
            add_button(controls, "Vol -", 10, 391, 102, 65, lambda: controller.volume(False))
            add_button(controls, "TDT", 134, 391, 104, 65, controller.live_tv)
            add_button(controls, "Canal -", 258, 391, 102, 65, lambda: controller.channel(False))

            add_button(controls, "Aplicaciones", 5, 480, 112, 50, lambda: load_page("apps"))
            add_button(controls, "Entradas HDMI", 127, 480, 116, 50, lambda: load_page("inputs"))
            add_button(controls, "Brillo / Imagen", 253, 480, 112, 50, lambda: dispatch(controller.picture_settings))
        else:
            add_button(controls, "< Mando", 10, 0, 110, 50, lambda: show_page("remote"))
            entries = controller.apps if name == "apps" else controller.inputs
            for i, (title, item_id) in enumerate(entries[offset: offset + 7]):
                func = (lambda item_id=item_id: controller.launch_app(item_id)) if name == "apps" else (
                    lambda item_id=item_id: controller.switch_input(item_id))
                add_button(controls, title[:28], 14, 63 + i * 62, 342, 55, func)
            if offset > 0:
                add_button(controls, "Anterior", 8, 516, 160, 52, lambda: show_page(name, max(0, offset-7)))
            if len(entries) > offset + 7:
                add_button(controls, "Siguiente", 190, 516, 170, 52, lambda: show_page(name, offset+7))
            if not entries:
                tell("Lista vacia o sin permiso. Comprueba la conexion.")

    def load_page(name):
        if name == "apps":
            def task():
                controller.list_apps()
                show_page("apps")
            dispatch(task)
        else:
            def task():
                controller.list_inputs()
                show_page("inputs")
            dispatch(task)

    def connect():
        addr = ip_field.text.strip()
        def task():
            controller.connect(addr, message=tell)
            tell("LG conectado. Ya puedes usar el mando.")
        dispatch(task)

    connect_button = ui.Button(title="Conectar")
    connect_button.frame = (252, 65, 120, 44)
    connect_button.action = lambda sender: connect()
    screen.add_subview(connect_button)
    show_page()
    ui.show_view(screen, ui.PRESENTATION_MODE_SHEET)
    controller.close()
    executor.shutdown(wait=False)


def start_terminal():
    print("LG Remote+ - sin ordenador, directo desde este iPhone")
    addr = input("IP del LG [" + (controller.saved_ip() or "192.168.1.45") + "]: ").strip()
    addr = addr or controller.saved_ip()
    controller.connect(addr, message=print)
    print("Conectado. Comandos: up down left right ok back home vol+ vol- ch+ ch- "
          "mute tv off apps inputs img text salir")
    try:
        while True:
            cmd = input("LG> ").strip().lower()
            try:
                if cmd in ("salir", "exit", "q"):
                    break
                elif cmd in ("up", "down", "left", "right", "ok", "back", "home"):
                    controller.press({"ok": "ENTER"}.get(cmd, cmd.upper()))
                elif cmd == "vol+":
                    controller.volume(True)
                elif cmd == "vol-":
                    controller.volume(False)
                elif cmd == "ch+":
                    controller.channel(True)
                elif cmd == "ch-":
                    controller.channel(False)
                elif cmd == "mute":
                    controller.mute()
                elif cmd == "tv":
                    controller.live_tv()
                elif cmd == "off":
                    controller.power_off()
                elif cmd == "img":
                    controller.picture_settings()
                elif cmd == "apps":
                    apps = controller.list_apps()
                    for i, (title, _) in enumerate(apps):
                        print(i, title)
                    idx = int(input("Numero de app: "))
                    controller.launch_app(apps[idx][1])
                elif cmd == "inputs":
                    inputs = controller.list_inputs()
                    for i, (title, _) in enumerate(inputs):
                        print(i, title)
                    idx = int(input("Numero HDMI: "))
                    controller.switch_input(inputs[idx][1])
                elif cmd == "text":
                    controller.write_text(input("Texto: "))
                else:
                    print("Comando desconocido")
            except Exception as exc:
                print("ERROR:", exc)
    finally:
        controller.close()


if __name__ == "__main__":
    try:
        import pyto_ui
    except ImportError:
        start_terminal()
    else:
        start_pyto()
