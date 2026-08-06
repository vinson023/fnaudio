from __future__ import annotations

import json
import os
import socket
import time
from typing import Any, Dict, List, Tuple


TRIM_SOCKET_PATH = "/var/run/trim_open_gateway_apiscope.socket"
TRIM_API_PATH = "/api/v1/trimapp"
APP_NAME = "fnaudio"


class FnosApiError(RuntimeError):
    pass


def _http_payload(req: str, data: Dict[str, Any] | None = None, token: str | None = None) -> bytes:
    body = json.dumps(
        {
            "reqId": f"fnaudio-{int(time.time() * 1000)}",
            "req": req,
            "appName": APP_NAME,
            "data": data or {},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    token = token or os.environ.get("TRIM_API_TOKEN", "")
    if not token:
        raise FnosApiError("未获取到飞牛系统授权 token，请确认应用已声明目录授权权限并从飞牛应用入口打开")
    headers = [
        f"POST {TRIM_API_PATH} HTTP/1.1",
        "Host: trim-open-gateway",
        "Content-Type: application/json; charset=utf-8",
        f"Content-Length: {len(body)}",
        f"Authorization: Bearer {token}",
        "Connection: close",
        "",
        "",
    ]
    return "\r\n".join(headers).encode("utf-8") + body


def _parse_http_response(raw: bytes) -> Dict[str, Any]:
    header, _, body = raw.partition(b"\r\n\r\n")
    status_line = header.splitlines()[0].decode("iso-8859-1", "replace") if header else ""
    try:
        status = int(status_line.split()[1])
    except (IndexError, ValueError):
        status = 0
    if status < 200 or status >= 300:
        raise FnosApiError(f"飞牛授权接口返回异常：HTTP {status or 'unknown'}")
    try:
        return json.loads(body.decode("utf-8"))
    except ValueError as exc:
        raise FnosApiError("飞牛授权接口返回内容无法解析") from exc


def call_trim_api(req: str, data: Dict[str, Any] | None = None, token: str | None = None) -> Dict[str, Any]:
    if not os.path.exists(TRIM_SOCKET_PATH):
        raise FnosApiError("飞牛授权接口不可用：未找到系统 Unix Socket")
    request = _http_payload(req, data, token)
    chunks: List[bytes] = []
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(8)
        client.connect(TRIM_SOCKET_PATH)
        client.sendall(request)
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
    payload = _parse_http_response(b"".join(chunks))
    if int(payload.get("code", -1)) != 0:
        raise FnosApiError(str(payload.get("msg") or "飞牛授权接口调用失败"))
    return payload


def get_shared_accessible_folders(token: str | None = None) -> Tuple[List[str], Dict[str, Any]]:
    payload = call_trim_api("trim.file.getSharedAccessibleFolders", {}, token)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    raw_paths = data.get("paths", [])
    paths = [str(path).strip() for path in raw_paths if str(path).strip()]
    return paths, payload


def del_shared_accessible_folder(path: str, token: str | None = None) -> Dict[str, Any]:
    return call_trim_api("trim.file.delSharedAccessibleFolder", {"path": path}, token)


__all__ = [
    "FnosApiError",
    "call_trim_api",
    "get_shared_accessible_folders",
    "del_shared_accessible_folder",
]
