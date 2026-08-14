from __future__ import annotations

import socket
import threading
import time
import uuid
from typing import Callable, Iterable

from version import UPNP_SERVER


MULTICAST = ("239.255.255.250", 1900)


class SsdpService:
    """Best-effort SSDP responder and alive announcer for the two DLNA roles."""

    def __init__(self, base_url: Callable[[], str], roles: Iterable[str] = ("renderer", "server")):
        self.base_url = base_url
        self.roles = tuple(roles)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="fnaudio-ssdp", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._announce("ssdp:byebye")
        if self._thread:
            self._thread.join(timeout=1.5)

    def _targets(self, role: str):
        device = "urn:schemas-upnp-org:device:Media%s:1" % ("Renderer" if role == "renderer" else "Server")
        yield "upnp:rootdevice"
        yield device
        if role == "renderer":
            yield "urn:schemas-upnp-org:service:AVTransport:1"
            yield "urn:schemas-upnp-org:service:RenderingControl:1"
        else:
            yield "urn:schemas-upnp-org:service:ContentDirectory:1"
        yield "uuid:%s" % self._uuid(role)

    def _uuid(self, role: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, self.base_url() + "/" + role))

    def _location(self, role: str) -> str:
        return self.base_url().rstrip("/") + "/dlna/%s/description.xml" % role

    def _packet(self, role: str, target: str, nts: str = "ssdp:alive") -> bytes:
        usn = "uuid:%s" % self._uuid(role)
        if target != usn:
            usn += "::" + target
        return ("NOTIFY * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nCACHE-CONTROL: max-age=1800\r\nLOCATION: %s\r\nNT: %s\r\nNTS: %s\r\nSERVER: %s\r\nUSN: %s\r\n\r\n" % (self._location(role), target, nts, UPNP_SERVER, usn)).encode("utf-8")

    def _announce(self, nts: str) -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
                for role in self.roles:
                    for target in self._targets(role):
                        sock.sendto(self._packet(role, target, nts), MULTICAST)
        except OSError:
            pass

    def _run(self) -> None:
        self._announce("ssdp:alive")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", 1900))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(MULTICAST[0]) + socket.inet_aton("0.0.0.0"))
            sock.settimeout(1.0)
        except OSError:
            return
        last_announce = time.monotonic()
        try:
            while not self._stop.is_set():
                if time.monotonic() - last_announce > 900:
                    self._announce("ssdp:alive")
                    last_announce = time.monotonic()
                try:
                    data, address = sock.recvfrom(8192)
                except socket.timeout:
                    continue
                text = data.decode("utf-8", "ignore")
                if not text.upper().startswith("M-SEARCH"):
                    continue
                lines = {key.strip().lower(): value.strip() for key, value in (line.split(":", 1) for line in text.split("\r\n")[1:] if ":" in line)}
                target = lines.get("st", "")
                for role in self.roles:
                    for candidate in self._targets(role):
                        if target not in ("ssdp:all", candidate):
                            continue
                        response_target = candidate
                        usn = "uuid:%s" % self._uuid(role)
                        if response_target != usn:
                            usn += "::" + response_target
                        response = ("HTTP/1.1 200 OK\r\nCACHE-CONTROL: max-age=1800\r\nEXT:\r\nLOCATION: %s\r\nSERVER: %s\r\nST: %s\r\nUSN: %s\r\n\r\n" % (self._location(role), UPNP_SERVER, response_target, usn)).encode("utf-8")
                        sock.sendto(response, address)
        finally:
            sock.close()
