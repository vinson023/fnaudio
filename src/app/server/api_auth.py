from __future__ import annotations

import ipaddress


ALL_API_SCOPES = frozenset({
    "library.read",
    "playback.read",
    "playback.control",
    "state.read",
    "state.write",
    "settings.read",
    "settings.write",
    "files.read",
})
PUBLIC_API_PATHS = frozenset({"/api/health", "/api/access"})
PRIVATE_MEDIA_PREFIXES = ("/media/", "/cover/", "/metadata/artwork/")


def requires_resource_auth(path: str) -> bool:
    path = str(path or "").split("?", 1)[0]
    return path.startswith(PRIVATE_MEDIA_PREFIXES)


def required_scope(method: str, path: str) -> str:
    method = str(method or "GET").upper()
    path = str(path or "").split("?", 1)[0]
    if path in PUBLIC_API_PATHS:
        return ""
    if requires_resource_auth(path):
        return "library.read"
    if path == "/api/state/user":
        return "state.read" if method in ("GET", "HEAD") else "state.write"
    if path.startswith("/api/config/") or path.startswith("/api/metadata/"):
        return "settings.read" if method in ("GET", "HEAD") else "settings.write"
    if path.startswith("/api/fs/") or path == "/api/library/location":
        return "files.read" if method in ("GET", "HEAD") else "files.manage"
    if path.startswith(("/api/playback/", "/api/player/", "/api/upnp/", "/api/dac/", "/api/airplay/")):
        return "playback.read" if method in ("GET", "HEAD") else "playback.control"
    return "library.read" if method in ("GET", "HEAD") else "settings.write"


def authorize_api(client_host: str, method: str, path: str, token: str, scopes) -> tuple[bool, int, str, str]:
    scope = required_scope(method, path)
    if not scope:
        return True, 200, scope, ""
    try:
        if not ipaddress.ip_address(str(client_host or "")).is_loopback:
            return False, 403, scope, "direct LAN API access is not allowed"
    except ValueError:
        return False, 403, scope, "untrusted API peer"
    if not str(token or "").strip():
        return False, 401, scope, "fnOS authentication is required"
    granted = {str(value).strip() for value in (scopes or []) if str(value).strip()}
    if scope not in granted:
        return False, 403, scope, "API scope is not granted"
    return True, 200, scope, ""
