#!/usr/bin/env python3
import os
import json
import sys
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import subprocess


CGI_APP_BASE = "/cgi/ThirdParty/fnaudio/index.cgi/"
CGI_ENTRY_MARKER = "/index.cgi"
API_SCOPES = "library.read,playback.read,playback.control,state.read,state.write,settings.read,settings.write,files.read"


def normalize_path_info(path_info="", request_uri="", routed_path=""):
    """Resolve PATH_INFO consistently across CGI hosts.

    Some fnOS CGI setups expose PATH_INFO as only the script path while the
    actual suffix is present in REQUEST_URI. A trusted same-origin caller can
    also provide an explicit routed_path fallback. Prefer those sources so
    POST API calls are not proxied to the HTML entry point with HTTP 200.
    """
    candidates = [str(routed_path or ""), str(request_uri or ""), str(path_info or "")]
    root_seen = False
    for candidate in candidates:
        raw = candidate.split("?", 1)[0]
        if CGI_ENTRY_MARKER in raw:
            suffix = raw.split(CGI_ENTRY_MARKER, 1)[1] or "/"
            if suffix != "/":
                return suffix if suffix.startswith("/") else "/" + suffix
            root_seen = True
        elif raw.startswith("/") and raw != "/":
            return raw
    return "/" if root_seen or not candidates else "/"


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


def write_proxy_response(response, path_info):
    content_type = str(response.headers.get("Content-Type") or "")
    rewrite_index = path_info in ("/", "/index.html") and "text/html" in content_type.lower()
    body = inject_cgi_base(response.read()) if rewrite_index else None
    sys.stdout.write("Status: %s %s\r\n" % (response.status, response.reason))
    for key, value in response.headers.items():
        lower = key.lower()
        if lower in ("connection", "transfer-encoding", "server"):
            continue
        if rewrite_index and lower == "content-length":
            continue
        sys.stdout.write("%s: %s\r\n" % (key, value))
    if rewrite_index:
        sys.stdout.write("Content-Length: %s\r\n" % len(body))
    sys.stdout.write("\r\n")
    sys.stdout.flush()
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


def service_port():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(header("TRIM_PKGETC", ""), "config.json"),
        os.path.join(script_dir, "service_port.json"),
        "/var/packages/fnaudio/etc/config.json",
        "/var/apps/fnaudio/etc/config.json",
    ]
    for config_path in candidates:
        if not config_path:
            continue
        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                port = int(json.load(fh).get("server_port", 53199))
            if 1024 <= port <= 65535:
                return port
        except (OSError, ValueError, TypeError):
            continue
    return 53199


def trim_token():
    for name in ("TRIM_API_TOKEN", "HTTP_TRIM_TOKEN", "HTTP_X_TRIM_TOKEN", "HTTP_AUTHORIZATION", "HTTP_X_FNAUDIO_TRIM_TOKEN"):
        value = os.environ.get(name, "").strip()
        if not value:
            continue
        if value.lower().startswith("bearer "):
            value = value.split(None, 1)[1].strip()
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
        value = urllib.parse.unquote(raw_value.strip())
        if value.lower().startswith("bearer "):
            value = value.split(None, 1)[1].strip()
        if value:
            return value
    return ""


def trim_request(req, data=None):
    token = trim_token()
    if not token:
        return {"ok": False, "message": "未获取到飞牛系统授权 token", "token_source": "cgi"}
    payload = json.dumps({
        "reqId": "fnaudio-%s" % str(int(__import__("time").time() * 1000)),
        "req": req,
        "appName": "fnaudio",
        "data": data or {},
    }, ensure_ascii=False).encode("utf-8")
    request = b"\r\n".join([
        b"POST /api/v1/trimapp HTTP/1.1",
        b"Host: trim-open-gateway",
        b"Content-Type: application/json; charset=utf-8",
        ("Content-Length: %s" % len(payload)).encode("utf-8"),
        ("Authorization: Bearer %s" % token).encode("utf-8"),
        b"Connection: close",
        b"",
        b"",
    ]) + payload
    raw = []
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(8)
        client.connect("/var/run/trim_open_gateway_apiscope.socket")
        client.sendall(request)
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            raw.append(chunk)
    header, _, body = b"".join(raw).partition(b"\r\n\r\n")
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:
        return {"ok": False, "message": "飞牛授权接口返回异常：%s" % exc, "token_source": "cgi"}
    if int(payload.get("code", -1)) != 0:
        return {"ok": False, "message": str(payload.get("msg") or "飞牛授权接口调用失败"), "token_source": "cgi"}
    payload["ok"] = True
    payload["token_source"] = "cgi"
    return payload


def read_config_payload():
    candidates = [
        os.path.join(header("TRIM_PKGETC", ""), "config.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "service_port.json"),
    ]
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            continue
    return {}


def merge_paths(existing, incoming):
    merged = []
    seen = set()
    for value in list(existing or []) + list(incoming or []):
        path = str(value or "").strip()
        if not path or path in seen:
            continue
        seen.add(path)
        merged.append(path)
    return merged


def send_local_config_update(paths):
    config = read_config_payload()
    port = service_port()
    body = json.dumps({
        "library_path": "\n".join(paths),
    }, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/config/library",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Fnaudio-Trim-Token": trim_token(),
            "X-Fnaudio-Scopes": API_SCOPES,
        },
        method="POST",
    )
    try:
        response = urllib.request.urlopen(request, timeout=15)
        return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {"ok": False, "message": str(exc), "status": None, "config": config}


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
        subprocess.run([script, "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, env=env)
    except Exception as exc:
        return False, str(exc)
    return True, "start requested"


def local_service_ready(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
            return 200 <= response.status < 500
    except Exception:
        return False


def wait_for_service(port, seconds=6):
    deadline = time.time() + seconds
    while time.time() < deadline:
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
    path_info = normalize_path_info(
        header("PATH_INFO", ""),
        header("REQUEST_URI", ""),
        header("HTTP_X_FNAUDIO_PATH", ""),
    )

    if False and path_info == "/api/fnos/auth-debug":
        names = ("TRIM_API_TOKEN", "HTTP_TRIM_TOKEN", "HTTP_X_TRIM_TOKEN", "HTTP_AUTHORIZATION", "HTTP_X_FNAUDIO_TRIM_TOKEN")
        payload = {"ok": True, "sources": {name: bool(os.environ.get(name, "")) for name in names}, "usable": bool(trim_token())}
        sys.stdout.write("Status: 200 OK\r\nContent-Type: application/json; charset=utf-8\r\n\r\n")
        sys.stdout.write(json.dumps(payload, ensure_ascii=False))
        return
    if False and path_info == "/api/fnos/shared-folders":
        sys.stdout.write("Status: 200 OK\r\nContent-Type: application/json; charset=utf-8\r\n\r\n")
        sys.stdout.write(json.dumps(trim_request("trim.file.getSharedAccessibleFolders", {}), ensure_ascii=False))
        return
    if False and path_info == "/api/fnos/shared-folders/sync":
        result = trim_request("trim.file.getSharedAccessibleFolders", {})
        if not result.get("ok"):
            sys.stdout.write("Status: 200 OK\r\nContent-Type: application/json; charset=utf-8\r\n\r\n")
            sys.stdout.write(json.dumps(result, ensure_ascii=False))
            return
        paths = []
        if result.get("ok") and isinstance(result.get("data"), dict):
            paths = [str(path).strip() for path in result["data"].get("paths", []) if str(path).strip()]
        config = read_config_payload()
        current_paths = [str(p).strip() for p in (config.get("library_paths") or []) if str(p).strip()]
        merged_paths = merge_paths(current_paths, paths)
        update = send_local_config_update(merged_paths)
        result = {
            "ok": bool(update.get("ok")),
            "paths": update.get("status", {}).get("library_paths", merged_paths) if isinstance(update.get("status"), dict) else merged_paths,
            "authorized_paths": paths,
            "status": update.get("status"),
            "message": update.get("message") or "已同步飞牛授权目录",
            "token_source": result.get("token_source", "cgi"),
        }
        sys.stdout.write("Status: 200 OK\r\nContent-Type: application/json; charset=utf-8\r\n\r\n")
        sys.stdout.write(json.dumps(result, ensure_ascii=False))
        return
    if False and path_info == "/api/fnos/shared-folders/delete":
        length = int(header("CONTENT_LENGTH", "0") or "0")
        body = sys.stdin.buffer.read(length) if length else b"{}"
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = {}
        path_value = str(payload.get("path") or "")
        result = trim_request("trim.file.delSharedAccessibleFolder", {"path": path_value})
        if result.get("ok"):
            config = read_config_payload()
            current_paths = [str(p).strip() for p in (config.get("library_paths") or []) if str(p).strip()]
            current_paths = [p for p in current_paths if p != path_value]
            send_local_config_update(current_paths)
        sys.stdout.write("Status: 200 OK\r\nContent-Type: application/json; charset=utf-8\r\n\r\n")
        sys.stdout.write(json.dumps(result, ensure_ascii=False))
        return
    query = header("QUERY_STRING")
    port = service_port()
    target = "http://127.0.0.1:%s" % port + path_info
    if query:
        target += "?" + query

    length = int(header("CONTENT_LENGTH", "0") or "0")
    body = sys.stdin.buffer.read(length) if length else None
    request_headers = {}
    for env_name, http_name in (
        ("CONTENT_TYPE", "Content-Type"),
        ("HTTP_RANGE", "Range"),
        ("HTTP_ACCEPT", "Accept"),
        ("HTTP_HOST", "X-Forwarded-Host"),
        ("HTTP_X_FORWARDED_PROTO", "X-Forwarded-Proto"),
        ("REMOTE_ADDR", "X-Forwarded-For"),
        ("HTTP_X_FORWARDED_FOR", "X-Forwarded-For"),
        ("HTTP_X_REAL_IP", "X-Real-IP"),
    ):
        value = header(env_name)
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
            method=header("REQUEST_METHOD", "GET"),
        )

    try:
        response = urllib.request.urlopen(build_request(), timeout=60)
        write_proxy_response(response, path_info)
    except urllib.error.HTTPError as exc:
        sys.stdout.write("Status: %s %s\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n" % (exc.code, exc.reason))
        sys.stdout.write("fnAudio service error: %s" % exc.reason)
    except urllib.error.URLError as exc:
        start_ok, start_message = try_start_service()
        if start_ok and wait_for_service(port):
            try:
                response = urllib.request.urlopen(build_request(), timeout=60)
                write_proxy_response(response, path_info)
                return
            except Exception as retry_exc:
                write_service_unavailable(port, "%s; auto-start retry failed: %s" % (exc, retry_exc))
                return
        write_service_unavailable(port, "%s; auto-start: %s" % (exc, start_message))
    except Exception as exc:
        write_service_unavailable(port, exc)


if __name__ == "__main__":
    main()
