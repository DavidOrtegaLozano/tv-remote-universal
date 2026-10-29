import importlib.util
import base64
import hashlib
import json
from pathlib import Path
import socket
import struct
import threading
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("lg_iphone", Path(__file__).resolve().parents[1] / "iphone" / "lg_remote_iphone.py")
lg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lg)

class SocketTest(unittest.TestCase):
    def test_ip_rejects_public_addresses(self):
        self.assertEqual(lg.validate_ip("192.168.1.50"), "192.168.1.50")
        with self.assertRaises(ValueError):
            lg.validate_ip("8.8.8.8")
        with self.assertRaises(ValueError):
            lg.validate_ip("not-an-ip")

    def test_ws_handshake_and_masked_frames(self):
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        received = []
        def read_all(sock, n):
            data = b""
            while len(data) < n:
                part = sock.recv(n-len(data))
                if not part:
                    raise EOFError
                data += part
            return data
        def run():
            conn, _ = server.accept()
            with conn:
                data = b""
                while b"\r\n\r\n" not in data:
                    data += conn.recv(4096)
                key = next(line.split(b":",1)[1].strip().decode() for line in data.split(b"\r\n") if line.lower().startswith(b"sec-websocket-key:"))
                accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
                conn.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: " + accept + "\r\n\r\n").encode())
                h = read_all(conn,2)
                self.assertTrue(h[1] & 0x80)
                length = h[1] & 0x7f
                mask = read_all(conn,4)
                payload = read_all(conn,length)
                received.append(bytes(b ^ mask[i%4] for i,b in enumerate(payload)).decode())
                response = json.dumps({"type":"response", "payload":{"returnValue":True}}).encode()
                conn.sendall(bytes([0x81, len(response)]) + response)
            server.close()
        worker = threading.Thread(target=run)
        worker.start()
        ws = lg.TVWebSocket("ws://127.0.0.1:" + str(port))
        ws.send('{"test":1}')
        result = json.loads(ws.receive())
        self.assertEqual(result["type"], "response")
        ws.close()
        worker.join(timeout=3)
        self.assertEqual(received, ['{"test":1}'])

    def test_call_uses_unique_message_id_and_checks_errors(self):
        class Fake:
            def __init__(self):
                self.sent=[]
            def send(self, msg):
                self.sent.append(json.loads(msg))
            def receive(self):
                return json.dumps({"type":"response","id":self.sent[-1]["id"],"payload":{"returnValue":True,"answer":42}})
        controller=lg.LGController()
        controller.ws=Fake()
        self.assertEqual(controller.call("ssap://test")["answer"], 42)
        self.assertEqual(controller.call("ssap://other")["answer"], 42)
        self.assertNotEqual(controller.ws.sent[0]["id"],controller.ws.sent[1]["id"])

if __name__=="__main__":
    unittest.main()
