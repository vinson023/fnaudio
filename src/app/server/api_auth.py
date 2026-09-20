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
TRUSTED_LAN_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    "10.0.0.0/8",
    "172.16.0.0/12",
    "198.51.100.0/16",
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


def authorize_api(client_host: str, method: str, path: str, token: str, scopes) -> tuple[bool, int, str, str]:
    scope = required_scope(method, path)
    if not scope:
        return True, 200, scope, ""
    try:
        peer = ipaddress.ip_address(client_host.strip() if isinstance(client_host, str) else "")
        # The package exposes its own port for trusted LAN controllers. Keep
        # Public addresses stay behind fnOS/Android authentication. LAN media
        # browsing and playback remain available to direct controllers, while
        # destructive configuration/file writes must use the fnOS CGI entry.
        if not peer.is_loopback and any(peer in network for network in TRUSTED_LAN_NETWORKS):
            if scope in PRIVILEGED_WRITE_SCOPES:
                return False, 403, scope, "fnOS authenticated application entry is required"
            return True, 200, scope, ""
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
