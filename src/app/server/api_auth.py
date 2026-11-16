from __future__ import annotations

import ipaddress

from api_route_policy import (
    PUBLIC_API_PATHS,
    PRIVATE_MEDIA_PREFIXES,
    normalize_path,
    required_scope,
    requires_resource_auth,
)

ALL_API_SCOPES = frozenset({
    "library.read",
    "playback.read",
    "playback.control",
    "state.read",
    "state.write",
    "settings.read",
    "settings.write",
    "files.read",
    "files.manage",
})
# The only thing a LAN peer may reach without an fnOS identity is UPnP/DLNA.
#
# The packaged port answers outside the fnOS gateway, so a request that arrives
# there never passed an authentication step. R563 tried to make that mode useful
# by allowing reads; that still handed the whole library, the player and the
# favourites to every device on the network. It is now shut. The exception is the
# casting surface: a television or speaker fetches /upnp/media/... and the device
# description under /dlna/ directly, over plain HTTP with no credentials to offer,
# so blocking those would not secure anything - it would just stop playback.
ANONYMOUS_LAN_PREFIXES = ("/dlna/", "/upnp/media/", "/upnp/cover/")

# Said to the browser and to the API alike; the settings UI repeats it nowhere,
# because a direct client never gets far enough to render a page.
DIRECT_ACCESS_DENIED = "禁止直连访问：请从飞牛应用中心打开 fnAudio（DLNA 投播不受影响）"

TRUSTED_LAN_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    "10.0.0.0/8",
    "172.16.0.0/12",
    # 192.168/16 is the most common home LAN range in the world and the one the
    # packaged port is normally opened from ("http://192.168.x.y:3131"). Leaving
    # it out meant every API call from that client got 403 "direct LAN API access
    # is not allowed" while loopback (the CGI entry) kept working, so the same
    # install looked healthy in fnOS and empty when opened directly.
    "192.168.0.0/16",
    # Carrier-grade NAT, which several home routers hand out as their LAN range.
    "100.64.0.0/10",
    "198.51.0.0/16",
    "169.254.0.0/16",
    "fc00::/7",
    "fe80::/10",
))


def _granted_scopes(scopes):
    if not isinstance(scopes, (list, tuple, set, frozenset)):
        return frozenset()
    granted = set()
    for value in scopes:
        if len(granted) >= len(ALL_API_SCOPES):
            break
        if not isinstance(value, str) or len(value) > 128:
            continue
        scope = value.strip()
        if scope in ALL_API_SCOPES:
            granted.add(scope)
    return frozenset(granted)


def _normalized_peer(client_host):
    """The peer address with IPv4-mapped IPv6 folded down, or None."""
    try:
        peer = ipaddress.ip_address(client_host.strip() if isinstance(client_host, str) else "")
    except ValueError:
        return None
    # A dual-stack listener reports an IPv4 peer as ::ffff:a.b.c.d, and that
    # address is not a member of any IPv4 network, so a LAN client behind an IPv6
    # socket would have been judged untrusted. Normalise before any check.
    if isinstance(peer, ipaddress.IPv6Address) and peer.ipv4_mapped is not None:
        return peer.ipv4_mapped
    return peer


def anonymous_lan_route(method: str, path: str) -> bool:
    """True for the UPnP surface a renderer fetches without credentials."""
    if (method.upper() if isinstance(method, str) else "") not in ("GET", "HEAD"):
        return False
    return normalize_path(path).startswith(ANONYMOUS_LAN_PREFIXES)


def peer_may_reach(client_host, method: str, path: str) -> bool:
    """Whether this peer is allowed to touch the route at all.

    Loopback is the fnOS gateway (and the CGI relay), which is the only channel
    that carries a verified identity. A LAN peer gets the UPnP surface and nothing
    else - not the page, not the API, not the static assets.
    """
    peer = _normalized_peer(client_host)
    if peer is None:
        return False
    if peer.is_loopback:
        return True
    if not any(peer in network for network in TRUSTED_LAN_NETWORKS):
        return False
    return anonymous_lan_route(method, path)


def authorize_api(client_host: str, method: str, path: str, token: str, scopes) -> tuple[bool, int, str, str]:
    scope = required_scope(method, path)
    if not scope:
        return True, 200, scope, ""
    peer = _normalized_peer(client_host)
    if peer is None:
        return False, 403, scope, "untrusted API peer"
    if not peer.is_loopback:
        # 403, not 401: there is no credential this client can present. The only
        # way in is the fnOS entry, which is a different URL, not a different
        # header.
        if not any(peer in network for network in TRUSTED_LAN_NETWORKS):
            return False, 403, scope, "public access is not allowed"
        if anonymous_lan_route(method, path):
            return True, 200, scope, ""
        return False, 403, scope, DIRECT_ACCESS_DENIED
    if not isinstance(token, str) or not token.strip():
        return False, 401, scope, "fnOS authentication is required"
    granted = _granted_scopes(scopes)
    if scope not in granted:
        return False, 403, scope, "API scope is not granted"
    return True, 200, scope, ""
