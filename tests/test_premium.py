"""Test SSDP parsing and premium UI wiring without Pyto or a television."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]/"iphone"
def load(filename,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/filename)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module

discovery=load("lg_discovery.py","lg_discovery")

class DiscoveryTests(unittest.TestCase):
    def test_parse_valid_ssdp(self):
        pkt=(b"HTTP/1.1 200 OK\r\n"
             b"ST: urn:lge-com:service:webos-second-screen:1\r\n"
             b"LOCATION: http://192.168.1.49:3000/description.xml\r\n\r\n")
        tv=discovery.parse_ssdp(pkt,"192.168.1.49")
        self.assertEqual(tv["ip"],"192.168.1.49")
        self.assertEqual(tv["source"],"SSDP")

    def test_ignore_non_lg_and_public_address(self):
        pkt=b"HTTP/1.1 200 OK\r\nST: upnp:rootdevice\r\nSERVER: Other\r\n\r\n"
        self.assertIsNone(discovery.parse_ssdp(pkt,"192.168.1.10"))
        self.assertIsNone(discovery.parse_ssdp(b"HTTP/1.1 200 OK\r\nST: urn:lge-com:service:webos-second-screen:1\r\n\r\n","8.8.8.8"))

    def test_known_saved_tv(self):
        with patch.object(discovery,"discover_ssdp",return_value=[]),patch.object(discovery,"probe_port",return_value=True),patch.object(discovery,"discover_subnet",return_value=[]):
            values=discovery.discover_tvs(saved_ip="192.168.0.42")
            self.assertEqual(values[0]["ip"],"192.168.0.42")

class UIStub:
    def __init__(self,**kwargs):
        self.subviews=[]
        self.text=kwargs.get("text","")
        self.title=kwargs.get("title","")
        self.size=(375,810)
    def add_subview(self,x):self.subviews.append(x)
    def remove_subview(self,x):self.subviews.remove(x)
class Color:
    @staticmethod
    def rgb(*channels):return channels

class FakeController:
    def __init__(self):
        self.apps=[("Netflix","app.netflix")]
        self.inputs=[("HDMI 1","HDMI_1")]
    def saved_ip(self):return "192.168.1.12"
    def close(self):pass

class UiTests(unittest.TestCase):
    def test_main_pages_render(self):
        lib=types.ModuleType("pyto_ui")
        lib.View=UIStub;lib.Button=UIStub;lib.Label=UIStub;lib.TextField=UIStub
        lib.Color=Color;lib.Font=lambda *args:args;lib.PRESENTATION_MODE_SHEET=1
        mt=types.ModuleType("mainthread");mt.mainthread=lambda callback:callback
        lg=types.ModuleType("lg_remote_iphone");lg.LGController=FakeController
        with patch.dict(sys.modules,{"pyto_ui":lib,"mainthread":mt,"lg_remote_iphone":lg}):
            appmodule=load("LG_REMOTE_PLUS.py","LG_REMOTE_PLUS_mock")
            with patch.object(appmodule,"discover_tvs",return_value=[{"ip":"192.168.1.9","name":"Mi LG","source":"SSDP"}]):
                app=appmodule.PremiumRemote()
                app.worker.shutdown(wait=True)
            self.assertEqual(app.devices[0]["name"],"Mi LG")
            for page in ("tvs","remote","apps","inputs"):
                app.page=page
                app.draw()
                self.assertGreater(len(app.body.subviews),1)
            app.alive=False

if __name__=="__main__":unittest.main()
