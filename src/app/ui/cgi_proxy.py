#!/usr/bin/env python3
import os
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import subprocess


CGI_APP_BASE = "/cgi/ThirdParty/fnaudio/index.cgi/"
MAX_REWRITTEN_INDEX_BYTES = 16 * 1024 * 1024
MAX_LOCAL_CONFIG_BYTES = 2 * 1024 * 1024
MAX_PROXY_REQUEST_BODY_BYTES = 2 * 1024 * 1024
MAX_PROXY_QUERY_STRING_CHARS = 64 * 1024
MAX_PROXY_QUERY_FIELDS = 256
MAX_TRIM_TOKEN_CHARS = 8192
MAX_PROXY_RESPONSE_HEADERS = 64
MAX_PROXY_RESPONSE_HEADER_NAME_CHARS = 128
MAX_PROXY_RESPONSE_HEADER_VALUE_CHARS = 8192
MAX_PROXY_REQUEST_HEADER_VALUE_CHARS = 4096
MAX_PROXY_ROUTE_CHARS = 4096
CGI_ENTRY_MARKER = "/index.cgi"
API_SCOPES = "library.read,playback.read,playback.control,state.read,state.write,settings.read,settings.write,files.read,files.manage"
ROUTE_QUERY_PARAMETER = "__fnaudio_path"
ALLOWED_PROXY_METHODS = frozenset(("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"))
_RESPONSE_HEADER_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")


def proxy_request_header_value(value, maximum=MAX_PROXY_REQUEST_HEADER_VALUE_CHARS):
    """Keep CGI-provided forwarding headers bounded and header-safe."""
    if not isinstance(value, str):
        return ""
    try:
        limit = int(maximum)
    except (TypeError, ValueError, OverflowError):
        limit = MAX_PROXY_REQUEST_HEADER_VALUE_CHARS
    if limit < 1:
        return ""
    value = value.strip()
    if not value or len(value) > limit:
        return ""
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return ""
    return value


def _safe_proxy_route(value):
    """Return a path-safe CGI route, ``None`` for an unsafe supplied value."""
    if not isinstance(value, str):
        return None
    route = value.split("?", 1)[0]
    if not route:
        return ""
    if len(route) > MAX_PROXY_ROUTE_CHARS or not route.startswith("/"):
        return None
    try:
        decoded = urllib.parse.unquote(route)
    except Exception:
        return None
    if (not decoded.startswith("/") or "\\" in decoded
            or any(ord(character) < 32 or ord(character) == 127 for character in decoded)):
        return None
    if any(segment in (".", "..") for segment in decoded.split("/")):
        return None
    return route


def normalize_path_info(path_info="", request_uri="", routed_path=""):
    """Resolve PATH_INFO consistently across CGI hosts.

    Some fnOS CGI setups expose PATH_INFO as only the script path while the
    actual suffix is present in REQUEST_URI. A trusted same-origin caller can
    also provide an explicit routed_path fallback. Prefer those sources so
    POST API calls are not proxied to the HTML entry point with HTTP 200.
    """
    explicit_route = _safe_proxy_route(routed_path)
    if explicit_route is None:
        # An explicit Android/header route has priority over PATH_INFO. Do not
        # let an unsafe explicit route silently fall through to an unrelated
        # host-provided request URI.
        return "/"
    if explicit_route:
        if CGI_ENTRY_MARKER in explicit_route:
            explicit_route = explicit_route.split(CGI_ENTRY_MARKER, 1)[1] or "/"
        safe_explicit_route = _safe_proxy_route(explicit_route)
        return safe_explicit_route if safe_explicit_route is not None else "/"
    candidates = [request_uri, path_info]
    root_seen = False
    for candidate in candidates:
        raw = _safe_proxy_route(candidate)
        if raw is None:
            continue
        if not raw:
            continue
        if CGI_ENTRY_MARKER in raw:
            suffix = raw.split(CGI_ENTRY_MARKER, 1)[1] or "/"
            if suffix != "/":
                safe_suffix = _safe_proxy_route(suffix)
                if safe_suffix is not None:
                    return safe_suffix
                continue
            root_seen = True
        elif raw.startswith("/") and raw != "/":
            return raw
    return "/" if root_seen or not candidates else "/"


def extract_routed_query(query_string=""):
    """Remove Android's CGI route parameter while preserving API query data."""
    if not isinstance(query_string, str) or len(query_string) > MAX_PROXY_QUERY_STRING_CHARS:
        return "", ""
    routed_path = ""
    forwarded = []
    try:
        pairs = urllib.parse.parse_qsl(
            query_string, keep_blank_values=True, max_num_fields=MAX_PROXY_QUERY_FIELDS,
        )
    except (TypeError, ValueError, OverflowError):
        return "", ""
    for name, value in pairs:
        if name == ROUTE_QUERY_PARAMETER and not routed_path:
            routed_path = value
        else:
            forwarded.append((name, value))
    return routed_path, urllib.parse.urlencode(forwarded, doseq=True)


def inject_cgi_base(body):
    if not body or b"<base " in body[:4096].lower():
        return body
    marker = b"<head>"
    index = body.lower().find(marker)
    if index < 0:
        return body
    insert_at = index + len(marker)
    tag = ('\n  <base href="%s">' % CGI_APP_BASE).encode("utf-8")
    return body[:insert_at] + tag + body[insert_at:]


def proxy_response_status(response):
    """Return CGI-safe backend status components without coercing objects."""
    status = getattr(response, "status", getattr(response, "code", 502))
    if isinstance(status, bool) or not isinstance(status, int) or not 100 <= status <= 599:
        return 502, "Bad Gateway"
    reason = getattr(response, "reason", "")
    if not isinstance(reason, str):
        reason = ""
    reason = reason.strip()
    if len(reason) > 256 or "\r" in reason or "\n" in reason:
        reason = ""
    return status, reason or "OK"


def proxy_response_headers(headers, rewrite_index=False):
    """Filter backend headers before writing raw CGI response lines."""
    try:
        entries = headers.items()
    except Exception:
        return []
    accepted = []
    try:
        for key, value in entries:
            if len(accepted) >= MAX_PROXY_RESPONSE_HEADERS:
                break
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            name = key.strip()
            header_value = value.strip()
            lower = name.lower()
            if (not name or len(name) > MAX_PROXY_RESPONSE_HEADER_NAME_CHARS
                    or not _RESPONSE_HEADER_NAME.fullmatch(name)
                    or len(header_value) > MAX_PROXY_RESPONSE_HEADER_VALUE_CHARS
                    or "\r" in header_value or "\n" in header_value):
                continue
            if lower in ("connection", "transfer-encoding", "server"):
                continue
            # The index body is read and modified below. A backend
            # Content-Encoding would describe the original compressed bytes,
            # not the rewritten plaintext body, and would make the browser
            # attempt to decompress/inject an already-invalid response.
            if rewrite_index and lower in ("content-length", "content-encoding"):
                continue
            accepted.append((name, header_value))
    except Exception:
        pass
    return accepted


def write_proxy_response(response, path_info, head_only=False):
    headers = getattr(response, "headers", {})
    try:
        content_type = headers.get("Content-Type") if hasattr(headers, "get") else ""
    except Exception:
        content_type = ""
    content_type = content_type if isinstance(content_type, str) else ""
    rewrite_index = path_info in ("/", "/index.html") and "text/html" in content_type.lower()
    body = None
    if rewrite_index:
        raw = response.read(MAX_REWRITTEN_INDEX_BYTES + 1)
        if len(raw) > MAX_REWRITTEN_INDEX_BYTES:
            sys.stdout.write("Status: 413 Response Too Large\r\nContent-Length: 0\r\n\r\n")
            sys.stdout.flush()
            return
        body = inject_cgi_base(raw)
    status, reason = proxy_response_status(response)
    sys.stdout.write("Status: %s %s\r\n" % (status, reason))
    for key, value in proxy_response_headers(headers, rewrite_index):
        sys.stdout.write("%s: %s\r\n" % (key, value))
    if rewrite_index:
        sys.stdout.write("Content-Length: %s\r\n" % len(body))
    sys.stdout.write("\r\n")
    sys.stdout.flush()
    if head_only:
        return
    if rewrite_index:
        sys.stdout.buffer.write(body)
        sys.stdout.buffer.flush()
        return
    while True:
        chunk = response.read(256 * 1024)
        if not chunk:
            break
        sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()


def header(name, default=""):
    return os.environ.get(name, default)


def read_proxy_request_body(stream, raw_length, maximum=MAX_PROXY_REQUEST_BODY_BYTES):
    """Read CGI input only after validating and bounding CONTENT_LENGTH."""
    if raw_length is None or raw_length == "":
        length = 0
    elif isinstance(raw_length, int) and not isinstance(raw_length, bool):
        length = raw_length
    elif not isinstance(raw_length, str):
        raise ValueError("invalid content length")
    else:
        text = raw_length.strip()
        if not text or not text.isascii() or not text.isdecimal():
            raise ValueError("invalid content length")
        try:
            length = int(text, 10)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("invalid content length")
    if length < 0:
        raise ValueError("invalid content length")
    if length > maximum:
        raise OverflowError("request body is too large")
    if not length:
        return b""
    chunks = []
    remaining = length
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise ValueError("request body is truncated")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def service_port():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    config_root = header("TRIM_PKGETC", "").strip()
    if config_root:
        candidates.append(os.path.join(config_root, "config.json"))
    candidates.extend((
        os.path.join(script_dir, "service_port.json"),
        "/var/packages/fnaudio/etc/config.json",
        "/var/apps/fnaudio/etc/config.json",
    ))
    for config_path in candidates:
        if not config_path:
            continue
        try:
            if os.path.getsize(config_path) > MAX_LOCAL_CONFIG_BYTES:
                continue
            with open(config_path, "rb") as fh:
                raw = fh.read(MAX_LOCAL_CONFIG_BYTES + 1)
            if len(raw) > MAX_LOCAL_CONFIG_BYTES:
                continue
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                continue
            value = payload.get("server_port", 53199)
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                port = value
            elif isinstance(value, str) and value.strip().isascii() and value.strip().isdecimal():
                port = int(value.strip(), 10)
            else:
                continue
            if 1024 <= port <= 65535:
                return port
        except (OSError, ValueError, TypeError):
            continue
    return 53199


def normalize_trim_token(value):
    """Accept a bounded bearer token that is safe to place in an HTTP header."""
    if not isinstance(value, str):
        return ""
    token = value.strip()
    if token.lower().startswith("bearer "):
        token = token.split(None, 1)[1].strip()
    if not token or len(token) > MAX_TRIM_TOKEN_CHARS:
        return ""
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in token):
        return ""
    return token


def trim_token():
    for name in ("TRIM_API_TOKEN", "HTTP_TRIM_TOKEN", "HTTP_X_TRIM_TOKEN", "HTTP_AUTHORIZATION", "HTTP_X_FNAUDIO_TRIM_TOKEN"):
        value = normalize_trim_token(os.environ.get(name, ""))
        if value:
            return value
    cookie_header = os.environ.get("HTTP_COOKIE", "")
    accepted_cookie_names = {
        "fnaudio_trim_token",
        "trim_api_token",
        "trim_token",
        "fnos-token",
        "token",
    }
    for field in cookie_header.split(";"):
        name, separator, raw_value = field.strip().partition("=")
        if not separator or name.strip().lower() not in accepted_cookie_names:
            continue
        value = normalize_trim_token(urllib.parse.unquote(raw_value.strip()))
        if value:
            return value
    return ""


def appdest():
    explicit = header("TRIM_APPDEST", "")
    if explicit:
        return explicit
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for candidate in (
        os.path.abspath(os.path.join(script_dir, "..", "..")),
        os.path.abspath(os.path.join(script_dir, "..")),
        "/var/apps/fnaudio",
    ):
        if os.path.isfile(os.path.join(candidate, "cmd", "main")) or os.path.isdir(os.path.join(candidate, "target")):
            return candidate
    return ""


def try_start_service():
    root = appdest()
    if not root:
        return False, "missing TRIM_APPDEST"
    candidates = [
        os.path.join(root, "cmd", "main"),
        os.path.join(root, "..", "cmd", "main"),
        "/var/apps/fnaudio/cmd/main",
    ]
    script = next((path for path in candidates if os.path.isfile(path)), "")
    if not script:
        return False, "cmd/main not found"
    env = os.environ.copy()
    env.setdefault("TRIM_APPDEST", root)
    env.setdefault("TRIM_PKGETC", os.path.join(root, "etc"))
    env.setdefault("TRIM_PKGVAR", os.path.join(root, "var"))
    try:
        completed = subprocess.run(
            [script, "start"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            env=env,
        )
    except Exception as exc:
        return False, str(exc)
    if completed.returncode != 0:
        return False, "cmd/main start failed with exit code %s" % completed.returncode
    return True, "start requested"


def local_service_ready(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
            return 200 <= response.status < 500
    except Exception:
        return False


def wait_for_service(port, seconds=6):
    # An in-process wait must not follow the wall clock: fnOS can step the
    # system time while this CGI worker is polling, and a forward jump would
    # keep the browser request hanging long past ``seconds``.
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if local_service_ready(port):
            return True
        time.sleep(0.4)
    return local_service_ready(port)


def write_service_unavailable(port, error):
    sys.stdout.write("Status: 503 Service Unavailable\r\n")
    sys.stdout.write("Content-Type: text/html; charset=utf-8\r\n\r\n")
    sys.stdout.write(
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>fnAudio</title>"
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
        "background:#f5f7fb;color:#172033;margin:0;display:grid;place-items:center;"
        "min-height:100vh}.box{max-width:560px;background:#fff;border:1px solid #dfe5ee;"
        "border-radius:12px;padding:28px;box-shadow:0 18px 50px #1f29371a}"
        "h1{font-size:22px;margin:0 0 12px}p{line-height:1.7;color:#53606f}"
        "code{background:#eef3f8;padding:2px 6px;border-radius:6px;color:#172033}</style></head>"
        "<body><main class='box'><h1>fnAudio 服务未启动</h1>"
        "<p>当前入口正在连接 TCP 端口 <code>%s</code>，但连接被拒绝。</p>"
        "<p>可能原因：端口被其他应用占用，或 fnAudio 刚修改端口后尚未重新启动。</p>"
        "<p>请在飞牛应用中心停止并重新启动 fnAudio；如果仍然失败，请换一个未占用的 TCP 端口。</p>"
        "<p><small>原始错误：%s</small></p></main></body></html>"
        % (port, str(error).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    )


def main():
    routed_query_path, query = extract_routed_query(header("QUERY_STRING"))
    path_info = normalize_path_info(
        header("PATH_INFO", ""),
        header("REQUEST_URI", ""),
        header("HTTP_X_FNAUDIO_PATH", "") or routed_query_path,
    )

    port = service_port()
    target = "http://127.0.0.1:%s" % port + path_info
    if query:
        target += "?" + query

    method = str(header("REQUEST_METHOD", "GET") or "GET").strip().upper()
    if method not in ALLOWED_PROXY_METHODS:
        sys.stdout.write("Status: 405 Method Not Allowed\r\nAllow: GET, HEAD, POST, PUT, PATCH, DELETE\r\nContent-Length: 0\r\n\r\n")
        return

    try:
        body = read_proxy_request_body(sys.stdin.buffer, header("CONTENT_LENGTH", "0")) or None
    except ValueError:
        sys.stdout.write("Status: 400 Bad Request\r\nContent-Length: 0\r\n\r\n")
        return
    except OverflowError:
        sys.stdout.write("Status: 413 Request Entity Too Large\r\nContent-Length: 0\r\n\r\n")
        return
    request_headers = {}
    for env_name, http_name in (
        ("CONTENT_TYPE", "Content-Type"),
        ("HTTP_RANGE", "Range"),
        ("HTTP_ACCEPT", "Accept"),
        ("HTTP_HOST", "X-Forwarded-Host"),
        ("HTTP_X_FORWARDED_PROTO", "X-Forwarded-Proto"),
        ("REMOTE_ADDR", "X-Forwarded-For"),
    ):
        value = proxy_request_header_value(header(env_name))
        if value:
            request_headers[http_name] = value
    token = trim_token()
    request_headers["X-Fnaudio-Internal"] = "1"
    if token:
        request_headers["X-Fnaudio-Trim-Token"] = token
        request_headers["X-Fnaudio-Scopes"] = API_SCOPES

    def build_request():
        return urllib.request.Request(
            target,
            data=body,
            headers=request_headers,
            method=method,
        )

    try:
        with urllib.request.urlopen(build_request(), timeout=60) as response:
            write_proxy_response(response, path_info, method == "HEAD")
    except urllib.error.HTTPError as exc:
        # HTTPError is also a readable response object. Preserve the backend's
        # structured JSON body and request id so the UI can show the actual
        # validation or playback failure instead of a generic proxy message.
        with exc:
            write_proxy_response(exc, path_info, method == "HEAD")
    except urllib.error.URLError as exc:
        start_ok, start_message = try_start_service()
        if start_ok and wait_for_service(port):
            try:
                with urllib.request.urlopen(build_request(), timeout=60) as response:
                    write_proxy_response(response, path_info, method == "HEAD")
                return
            except Exception as retry_exc:
                write_service_unavailable(port, "%s; auto-start retry failed: %s" % (exc, retry_exc))
                return
        write_service_unavailable(port, "%s; auto-start: %s" % (exc, start_message))
    except Exception as exc:
        write_service_unavailable(port, exc)


if __name__ == "__main__":
    main()
