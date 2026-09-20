from __future__ import annotations

import ipaddress
import http.client
import math
import socket
import threading
import time
import urllib.request
from collections import OrderedDict
from urllib.parse import urlparse

MAX_DLNA_XML_BYTES = 1024 * 1024
MAX_DLNA_TIMEOUT_SECONDS = 10.0
# A renderer's callback/control endpoint is a LAN peer whose address barely moves,
# but every GENA notification, SOAP action and description fetch used to resolve it
# again, so one "Play" press paid the resolver twice and a slow or sleeping DNS
# server put that latency in front of every control action.
LAN_ADDRESS_CACHE_TTL_SECONDS = 5.0
LAN_ADDRESS_CACHE_LIMIT = 64
_LAN_ADDRESS_CACHE: "OrderedDict[tuple, tuple]" = OrderedDict()
_LAN_ADDRESS_CACHE_LOCK = threading.Lock()
# Traffic counters for the cache above.  R74 left it with no observable at all, which made
# "why was the first action after a peer moved slow?" impossible to answer after the fact.
# Counts are the entire surface: no hostnames, no addresses, nothing that could single a
# peer out, because this feeds the DLNA diagnostics payload that already has a contract
# against exposing device identity.
_LAN_ADDRESS_CACHE_STATS = {"hits": 0, "misses": 0, "expired": 0, "evictions": 0}


def _cache_key(hostname, port):
    return (str(hostname).lower(), int(port))


def clear_lan_address_cache():
    """Drop every remembered address. Tests that count resolver traffic need this."""
    with _LAN_ADDRESS_CACHE_LOCK:
        _LAN_ADDRESS_CACHE.clear()


def forget_lan_addresses(hostname, port):
    with _LAN_ADDRESS_CACHE_LOCK:
        _LAN_ADDRESS_CACHE.pop(_cache_key(hostname, port), None)


def lan_address_cache_size():
    with _LAN_ADDRESS_CACHE_LOCK:
        return len(_LAN_ADDRESS_CACHE)


def lan_address_cache_status():
    """Traffic counters for the LAN resolver cache, with nothing that names a peer.

    The counters are cumulative for the process, like the discovery counters on the same
    diagnostics page, so a caller comparing two readings is what reveals a one-off event
    such as "the first action after a peer moved was slow": that is `expired` climbing
    without anyone having to know which peer moved.  No hostname, address, or cache key
    leaves this function, which is the contract the DLNA diagnostics payload is held to.
    """
    with _LAN_ADDRESS_CACHE_LOCK:
        status = dict(_LAN_ADDRESS_CACHE_STATS)
        status["entries"] = len(_LAN_ADDRESS_CACHE)
    status["limit"] = LAN_ADDRESS_CACHE_LIMIT
    status["ttl_seconds"] = LAN_ADDRESS_CACHE_TTL_SECONDS
    return status


def _cached_lan_addresses(hostname, port):
    """Return one recently validated address set for this endpoint, resolving at most once per TTL.

    Only results produced by :func:`_lan_addresses` are ever stored, so every
    address here was classified as a LAN private/link-local address by this
    process, and :func:`fetch_lan` pins its socket to one of them: reusing the
    entry cannot send traffic to an address a fresh resolution would not have
    produced. Failures are deliberately *not* stored, so a peer that comes back is
    reachable on the next action, and a dial error evicts the entry so a peer that
    moved is re-resolved immediately instead of after the TTL.

    The lock guards only the two dictionary operations. ``getaddrinfo`` has no
    timeout of its own, so it runs with the lock released: holding it across the
    resolver would let one broken host stall every other DLNA request.
    """
    key = _cache_key(hostname, port)
    with _LAN_ADDRESS_CACHE_LOCK:
        entry = _LAN_ADDRESS_CACHE.get(key)
        if entry is not None and entry[0] > time.monotonic():
            _LAN_ADDRESS_CACHE.move_to_end(key)
            _LAN_ADDRESS_CACHE_STATS["hits"] += 1
            return entry[1]
        stale = entry is not None
    addresses = _lan_addresses(hostname, port)
    with _LAN_ADDRESS_CACHE_LOCK:
        # Counting happens inside the lock because the lock already guards the entry these
        # numbers describe; what keeps the sections short is that none of them does I/O.
        _LAN_ADDRESS_CACHE_STATS["misses"] += 1
        if stale:
            _LAN_ADDRESS_CACHE_STATS["expired"] += 1
        _LAN_ADDRESS_CACHE[key] = (time.monotonic() + LAN_ADDRESS_CACHE_TTL_SECONDS, addresses)
        _LAN_ADDRESS_CACHE.move_to_end(key)
        while len(_LAN_ADDRESS_CACHE) > LAN_ADDRESS_CACHE_LIMIT:
            _LAN_ADDRESS_CACHE.popitem(last=False)
            _LAN_ADDRESS_CACHE_STATS["evictions"] += 1
    return addresses


def _read_response_limited(response, maximum):
    """Read short network chunks until EOF without exceeding the budget."""
    body = bytearray()
    while len(body) <= maximum:
        chunk = response.read(maximum - len(body) + 1)
        if not isinstance(chunk, (bytes, bytearray)):
            raise ValueError("DLNA response exceeds the size limit")
        if not chunk:
            break
        body.extend(chunk)
        if len(body) > maximum:
            raise ValueError("DLNA response exceeds the size limit")
    return bytes(body)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def lan_http_url(value: str) -> str:
    """Validate a DLNA peer endpoint before the server makes an outbound request."""
    parsed, port = _parse_lan_http_url(value)
    _lan_addresses(parsed.hostname, port)
    return parsed.geturl()


def _parse_lan_http_url(value: str):
    if not isinstance(value, str):
        raise ValueError("DLNA endpoint must be a text URL")
    parsed = urlparse(value.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("DLNA endpoint must be an unauthenticated HTTP(S) URL")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise ValueError("DLNA endpoint has an invalid port") from exc
    if not 1 <= port <= 65535:
        raise ValueError("DLNA endpoint has an invalid port")
    return parsed, port


def _lan_addresses(hostname: str, port: int):
    try:
        addresses = {row[4][0] for row in socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise ValueError("DLNA endpoint host cannot be resolved") from exc
    if not addresses:
        raise ValueError("DLNA endpoint host cannot be resolved")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        # A renderer/controller must be another LAN peer. Loopback is local
        # to fnAudio itself, so accepting it lets a forged SSDP description
        # or GENA callback reach unrelated services bound on this host.
        if not (ip.is_private or ip.is_link_local) or ip.is_loopback or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
            raise ValueError("DLNA endpoint must resolve only to LAN addresses")
    return tuple(sorted(addresses))


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, *, pinned_address=None, **kwargs):
        super().__init__(host, timeout=timeout, **kwargs)
        self._pinned_address = pinned_address

    def connect(self):
        if self._tunnel_host:
            # A tunnel means a proxy owns the socket, so the validated LAN
            # address cannot be honoured. Fail closed before dialling out
            # rather than pinning a connection the caller believes is direct.
            raise ValueError("DLNA pinned connection cannot be proxied")
        address = self._pinned_address or self.host
        self.sock = socket.create_connection((address, self.port), self.timeout, self.source_address)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, *, pinned_address=None, **kwargs):
        super().__init__(host, timeout=timeout, **kwargs)
        self._pinned_address = pinned_address

    def connect(self):
        if self._tunnel_host:
            raise ValueError("DLNA pinned connection cannot be proxied")
        address = self._pinned_address or self.host
        self.sock = socket.create_connection((address, self.port), self.timeout, self.source_address)
        # SNI and certificate verification keep using the validated hostname;
        # only the socket target is pinned, so a certificate for the peer's
        # name still has to match even though the address came from our DNS.
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


class _PinnedHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, address):
        super().__init__()
        self._address = address

    def http_open(self, req):
        return self.do_open(_PinnedHTTPConnection, req, pinned_address=self._address)


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, address):
        super().__init__()
        self._address = address

    def https_open(self, req):
        return self.do_open(_PinnedHTTPSConnection, req, context=self._context,
                            pinned_address=self._address)


def optional_lan_http_url(value: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("DLNA endpoint must be a text URL")
    value = value.strip()
    return lan_http_url(value) if value else ""


def fetch_lan(request_or_url, timeout: float = 3, max_bytes: int = MAX_DLNA_XML_BYTES) -> bytes:
    url = request_or_url.full_url if isinstance(request_or_url, urllib.request.Request) else request_or_url
    parsed, port = _parse_lan_http_url(url)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout):
        raise ValueError("DLNA timeout is invalid")
    timeout = float(timeout)
    if not 0.1 <= timeout <= MAX_DLNA_TIMEOUT_SECONDS:
        raise ValueError("DLNA timeout is invalid")
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or not 1 <= max_bytes <= MAX_DLNA_XML_BYTES:
        raise ValueError("DLNA response size limit is invalid")
    addresses = _cached_lan_addresses(parsed.hostname, port)
    # Resolve once for policy and connection, then pin the socket to the
    # selected result. The request keeps the original hostname so Host and
    # HTTPS SNI remain correct while DNS cannot change the target at connect.
    pinned_address = addresses[0]
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _NoRedirect(),
        _PinnedHTTPHandler(pinned_address),
        _PinnedHTTPSHandler(pinned_address),
    )
    try:
        with opener.open(request_or_url, timeout=timeout) as response:
            response_url, response_port = _parse_lan_http_url(response.geturl())
            if (response_url.scheme, response_url.hostname, response_port) != (parsed.scheme, parsed.hostname, port):
                raise ValueError("DLNA response changed the validated endpoint")
            length = response.headers.get("Content-Length")
            declared_length = None
            if length:
                if not isinstance(length, str):
                    raise ValueError("DLNA response has an invalid size")
                text = length.strip()
                if not text or not text.isascii() or not text.isdecimal():
                    raise ValueError("DLNA response has an invalid size")
                try:
                    declared_length = int(text, 10)
                except (TypeError, ValueError, OverflowError):
                    raise ValueError("DLNA response has an invalid size")
                if declared_length < 0:
                    raise ValueError("DLNA response has an invalid size")
                if declared_length > max_bytes:
                    raise ValueError("DLNA response exceeds the size limit")
            body = _read_response_limited(response, max_bytes)
            if declared_length is not None and len(body) != declared_length:
                raise ValueError("DLNA response is truncated")
            return body
    except OSError:
        # The pinned address no longer reached the peer (it moved, or the lease
        # was lost). Forget it so the next action re-resolves instead of waiting
        # out the TTL; the caller still sees the original network error.
        forget_lan_addresses(parsed.hostname, port)
        raise
