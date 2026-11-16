from __future__ import annotations

import ipaddress

from api_route_policy import (
    PRIVILEGED_WRITE_SCOPES,
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
# Scopes a direct LAN client may use without an fnOS identity.
#
# The packaged port answers outside the fnOS gateway, so a request that arrives
# there has no user behind it. Browsing and listening are harmless; anything that
# changes state is not: tuning a playlist or moving playback is the same authority
# as sitting in front of the device. Reading stays open so the page is still
# usable from a phone that opened the address directly.
LAN_READ_SCOPES = frozenset({"library.read", "playback.read", "state.read"})

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


def authorize_api(client_host: str, method: str, path: str, token: str, scopes,
                  allow_lan_write: bool = False) -> tuple[bool, int, str, str]:
    scope = required_scope(method, path)
    if not scope:
        return True, 200, scope, ""
    try:
        peer = ipaddress.ip_address(client_host.strip() if isinstance(client_host, str) else "")
        # A dual-stack listener reports an IPv4 peer as ::ffff:a.b.c.d, and that
        # address is not a member of any IPv4 network, so a LAN client behind an
        # IPv6 socket would have been refused as an untrusted peer. Normalise
        # before the loopback and network checks.
        if isinstance(peer, ipaddress.IPv6Address) and peer.ipv4_mapped is not None:
            peer = peer.ipv4_mapped
        # The package exposes its own port for trusted LAN controllers. Keep
        # Public addresses stay behind fnOS/Android authentication. LAN media
        # browsing and playback remain available to direct controllers, while
        # destructive configuration/file writes must use the fnOS CGI entry.
        if not peer.is_loopback and any(peer in network for network in TRUSTED_LAN_NETWORKS):
            if scope in PRIVILEGED_WRITE_SCOPES:
                return False, 403, scope, "fnOS authenticated application entry is required"
            if allow_lan_write or scope in LAN_READ_SCOPES:
                return True, 200, scope, ""
            # Writes need a real identity. 401 (not 403) is deliberate: the client
            # is allowed to ask again with credentials, and the web UI turns this
            # into "open the app from fnOS to change anything".
            return False, 401, scope, "局域网直连为只读访问，修改需要从 fnOS 应用入口登录"
        if not peer.is_loopback:
            return False, 403, scope, "direct LAN API access is not allowed"
    except ValueError:
        return False, 403, scope, "untrusted API peer"
    if not isinstance(token, str) or not token.strip():
        return False, 401, scope, "fnOS authentication is required"
    granted = _granted_scopes(scopes)
    if scope not in granted:
        return False, 403, scope, "API scope is not granted"
    return True, 200, scope, ""
