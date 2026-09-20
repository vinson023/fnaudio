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
        self._lifecycle_lock = threading.RLock()

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            try:
                thread = threading.Thread(target=self._run, name="fnaudio-ssdp", daemon=True)
                # Publish before starting so a parallel initializer sees the
                # reservation during the narrow Thread.start() window.
                self._thread = thread
                thread.start()
            except Exception:
                if "thread" in locals() and self._thread is thread:
                    self._thread = None
                self._stop.set()
                raise

    def stop(self) -> None:
        with self._lifecycle_lock:
            self._stop.set()
            self._announce("ssdp:byebye")
            thread = self._thread
            if thread and thread is not threading.current_thread():
                try:
                    thread.join(timeout=1.5)
                except RuntimeError:
                    # A failed Thread.start() can leave a pre-registered,
                    # unstarted handle. It has no worker to join.
                    pass
            if self._thread is thread and (thread is None or not thread.is_alive()):
                self._thread = None

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

    def udn(self, role: str) -> str:
        """Return the exact UDN advertised for a local DLNA role."""
        return "uuid:%s" % self._uuid(role)

    def location(self, role: str) -> str:
        """Return the exact description URL advertised for a local DLNA role."""
        return self._location(role)

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
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", 1900))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(MULTICAST[0]) + socket.inet_aton("0.0.0.0"))
            sock.settimeout(1.0)
        except OSError:
            if sock is not None:
                sock.close()
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
                except OSError:
                    # A connected UDP socket can surface an ICMP-derived
                    # ConnectionResetError from an earlier reply to a host
                    # that already went away. That is transient: letting it
                    # escape would silence DLNA discovery until the next app
                    # restart because nothing re-creates this listener.
                    if self._stop.wait(0.25):
                        break
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
                        try:
                            sock.sendto(response, address)
                        except OSError:
                            # A disappearing renderer must not terminate the
                            # listener; continue serving later discoveries.
                            continue
        finally:
            sock.close()
