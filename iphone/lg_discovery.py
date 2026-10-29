"""Deteccion LG webOS en red local: SSDP + sondeo /24 como respaldo.
Solo biblioteca estandar. El sondeo de puertos no confirma por si solo la marca.
"""
import ipaddress
import socket
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

SSDP_GROUP = ("239.255.255.250", 1900)
SSDP_TARGETS = (
    "urn:lge-com:service:webos-second-screen:1",
    "urn:schemas-upnp-org:device:MediaRenderer:1",
)
MAX_RESULTS = 12


def private_ip(value):
    try:
        addr = ipaddress.ip_address(str(value).strip())
        return addr.version == 4 and addr.is_private and not addr.is_loopback
    except (ValueError, TypeError):
        return False


def parse_ssdp(packet, source_ip):
    """Return candidate only if SSDP explicitly identifies LG/webOS."""
    if not private_ip(source_ip):
        return None
    if isinstance(packet, bytes):
        packet = packet.decode("utf-8", "replace")
    lines = packet.replace("\r\n", "\n").split("\n")
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    fingerprint = " ".join(headers.get(k, "") for k in ("st", "usn", "server"))
    if not any(term in fingerprint.lower() for term in (
        "lge-com", "webos", "lg electronics", "lg tv", "lgtv",
    )):
        return None
    return {"ip": source_ip, "name": "LG webOS", "source": "SSDP",
            "location": headers.get("location", "")}


def friendly_name(candidate):
    location = candidate.get("location", "")
    if not location:
        return candidate["name"]
    try:
        url = urllib.parse.urlparse(location)
        if url.scheme != "http" or url.hostname != candidate["ip"]:
            return candidate["name"]
        if url.port not in (80, 3000, 3001, 8080, 9080):
            return candidate["name"]
        with urllib.request.urlopen(location, timeout=1.0) as response:
            xml = response.read(65536)
        tree = ET.fromstring(xml)
        manufacturer = " ".join(
            (node.text or "") for node in tree.iter()
            if node.tag.split("}")[-1] == "manufacturer"
        )
        if manufacturer and "lg" not in manufacturer.lower():
            return candidate["name"]
        for node in tree.iter():
            if node.tag.split("}")[-1] == "friendlyName" and node.text:
                return node.text.strip()[:48]
    except (OSError, ValueError, ET.ParseError):
        pass
    return candidate["name"]


def discover_ssdp(timeout=2.7):
    devices = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.bind(("0.0.0.0", 0))
        sock.settimeout(0.35)
        for target in SSDP_TARGETS:
            request = (
                "M-SEARCH * HTTP/1.1\r\n"
                "HOST: 239.255.255.250:1900\r\n"
                'MAN: "ssdp:discover"\r\n'
                "MX: 2\r\nST: " + target + "\r\n\r\n"
            )
            try:
                sock.sendto(request.encode("ascii"), SSDP_GROUP)
            except OSError:
                pass
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                message, sender = sock.recvfrom(8192)
            except socket.timeout:
                continue
            except OSError:
                break
            tv = parse_ssdp(message, sender[0])
            if tv:
                devices[tv["ip"]] = tv
                if len(devices) >= MAX_RESULTS:
                    break
    finally:
        sock.close()
    if devices:
        with ThreadPoolExecutor(max_workers=6) as pool:
            pairs = [(tv, pool.submit(friendly_name, tv)) for tv in devices.values()]
            for tv, future in pairs:
                try:
                    tv["name"] = future.result(timeout=1.4)
                except Exception:
                    pass
    return list(devices.values())


def local_ipv4():
    """UDP connect is routing-only: no data is sent to the public address."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("1.1.1.1", 80))
        ip = sock.getsockname()[0]
        if private_ip(ip):
            return ip
    except OSError:
        pass
    finally:
        sock.close()
    try:
        for result in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = result[4][0]
            if private_ip(ip):
                return ip
    except OSError:
        pass
    return None


def probe_port(ip, port=3001, timeout=0.30):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def discover_subnet(local_ip=None, progress=None):
    ip = local_ip or local_ipv4()
    if not ip or not private_ip(ip):
        return []
    # Typical home Wi-Fi subnet. Avoid broad scans on carrier/VPN networks.
    network = ipaddress.ip_network(ip + "/24", strict=False)
    if progress:
        progress("Buscando dispositivos en " + str(network) + "…")
    ips = [str(host) for host in network.hosts() if str(host) != ip]
    found = []
    with ThreadPoolExecutor(max_workers=32) as pool:
        futures = {pool.submit(probe_port, candidate, 3001): candidate for candidate in ips}
        for future in as_completed(futures):
            try:
                if future.result():
                    found.append({"ip": futures[future],
                                  "name": "Posible LG (verificar al conectar)",
                                  "source": "SONDEO"})
            except OSError:
                pass
    # LG older versions may only listen on WS/3000. Run fallback only if necessary.
    if not found:
        if progress:
            progress("Comprobando compatibilidad con webOS antiguo…")
        with ThreadPoolExecutor(max_workers=32) as pool:
            futures = {pool.submit(probe_port, candidate, 3000): candidate for candidate in ips}
            for future in as_completed(futures):
                try:
                    if future.result():
                        found.append({"ip": futures[future],
                                      "name": "Dispositivo en puerto 3000",
                                      "source": "SONDEO"})
                except OSError:
                    pass
    return sorted(found[:MAX_RESULTS], key=lambda tv: tuple(map(int, tv["ip"].split("."))))


def discover_tvs(saved_ip=None, progress=None, subnet_fallback=True):
    """SSDP first, then known TV and /24 scan when SSDP is unavailable."""
    results = {}
    if progress:
        progress("Buscando televisores LG en la Wi-Fi…")
    try:
        for tv in discover_ssdp():
            results[tv["ip"]] = tv
    except OSError:
        pass
    if saved_ip and private_ip(saved_ip):
        if saved_ip not in results and (probe_port(saved_ip, 3001) or probe_port(saved_ip, 3000)):
            results[saved_ip] = {"ip": saved_ip, "name": "LG guardado", "source": "GUARDADO"}
    if not results and subnet_fallback:
        for tv in discover_subnet(progress=progress):
            results[tv["ip"]] = tv
    return sorted(results.values(), key=lambda tv: (
        tv["source"] not in ("GUARDADO", "SSDP"), tv["name"].lower(), tv["ip"]
    ))[:MAX_RESULTS]
