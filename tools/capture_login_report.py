"""把抓包或 logcat 里的登录过程整理成一份可直接对比的报告。

两份输入：
  --dump    mitmdump 的文本导出（capture_official_login.ps1 用 --flow-detail 3 生成）
  --logcat  adb logcat 的文本（-Mode ourApp 生成）

输出一份 markdown：登录相关请求的路径、状态码、是否带访问码头、是否下发会话
Cookie；以及我们自己的失败阶段。README 式的结论不在这里下——报告只摆事实，
对比是看报告的人做。
"""

import argparse
import re
import sys
from pathlib import Path

# 判定「和登录有关」的证据：路径、请求头或响应头里任一处出现。
LOGIN_HINTS = (
    "access_code", "access-code", "user/login", "user/info", "authToken",
    "tokenLogin", "set-cookie", "os-access-code", "trim_token", "fnos-token",
)
# 一个 flow 的起始行，例如：`[200] GET https://host/path` 或 `12:00:00 [302] ...`
FLOW_START = re.compile(r"^\s*(?:\d{2}:\d{2}:\d{2}\s+)?\[(\d{3}|-)\]\s+([A-Z]+)\s+(\S+)")
COOKIE_LINE = re.compile(r"^\s*(?:<<|>>)\s*(set-cookie|cookie|x-access-code|:authority|host)\s*:\s*(.*)$", re.I)


def split_flows(text):
    """把 mitmdump 的平铺文本切成一跳一跳的块（宽松解析，格式变了也不会空手而归）。"""
    flows = []
    current = None
    for line in text.splitlines():
        start = FLOW_START.match(line)
        if start:
            if current:
                flows.append(current)
            current = {"status": start.group(1), "method": start.group(2), "url": start.group(3), "lines": [line]}
            continue
        if current is not None:
            current["lines"].append(line)
    if current:
        flows.append(current)
    return flows


def is_login_flow(flow):
    blob = "\n".join(flow["lines"]).lower()
    return any(hint.lower() in blob for hint in LOGIN_HINTS)


def cookie_facts(flow):
    """这一跳带没带访问码、下发没下发会话 cookie。"""
    request_code = []
    cookies = []
    for line in flow["lines"]:
        match = COOKIE_LINE.match(line)
        if not match:
            continue
        name = match.group(1).lower()
        value = match.group(2).strip()
        if name == "x-access-code":
            request_code.append("present" if value else "empty")
        elif name == "set-cookie":
            pair = value.split(";", 1)[0]
            cookies.append("set: " + pair[:56] + ("…" if len(pair) > 56 else ""))
        elif name == "cookie":
            cookies.append("sent: " + pair_summary(value))
    return request_code, cookies


def pair_summary(value):
    names = []
    for part in value.split(";"):
        part = part.strip()
        if "=" in part:
            names.append(part.split("=", 1)[0])
    return ", ".join(names[:8]) + ("…" if len(names) > 8 else "")


def describe_flow(flow):
    code, cookies = cookie_facts(flow)
    lines = [
        "### %s %s" % (flow["method"], flow["url"]),
        "",
        "- 状态：`%s`" % flow["status"],
        "- 请求访问码头：%s" % (", ".join(code) if code else "未出现"),
        "- 会话 Cookie：%s" % (", ".join(cookies) if cookies else "**无 Set-Cookie**"),
    ]
    host = re.match(r"^[a-z]+://([^/]+)", flow["url"], re.I)
    if host:
        lines.append("- 目标主机：`%s`" % host.group(1))
    path = flow["url"]
    if "/p/" in path:
        lines.append("- 路径带 `/p/` 隧道前缀：**是**（官方 App 的外网路径形态）")
    else:
        lines.append("- 路径带 `/p/` 隧道前缀：否")
    return "\n".join(lines)


def report_from_dump(dump_path):
    text = dump_path.read_text(encoding="utf-8", errors="replace")
    flows = split_flows(text)
    login = [flow for flow in flows if is_login_flow(flow)]
    parts = [
        "# 登录抓包报告",
        "",
        "来源：`%s`" % dump_path.name,
        "",
        "- 抓到的请求总数：%d" % len(flows),
        "- 与登录相关：%d" % len(login),
    ]
    hosts = sorted({re.sub(r"^[a-z]+://([^/]+).*$", r"\1", flow["url"], flags=re.I) for flow in flows})
    if hosts:
        parts.append("- 目标主机：" + "、".join("`%s`" % host for host in hosts[:8]))
    if not login:
        parts += [
            "",
            "> 没有匹配到登录相关的请求。多半是 App 把 HTTP 走了本机隧道（不经系统代理），",
            "> 或者这次没有真正发生登录（只打开了 App）。换一次完整的 FN ID 登录再抓。",
        ]
    for flow in login[:40]:
        parts += ["", describe_flow(flow)]
    parts += [
        "",
        "## 怎么读这份报告",
        "",
        "1. **有没有 `/p/` 前缀**：官方外网走隧道时路径形如 `/p/api/v1/...`；我们直连时是",
        "   `/api/...`。前缀不同意味着网关前面还有一跳代理，它可能改写响应头。",
        "2. **`Set-Cookie` 出现在哪一跳**：如果它出现在 301/302 那一跳，而最终 200 没有，",
        "   就是「跟随重定向丢 cookie」——fnAudio 已在 R555 手动逐跳跟随。",
        "3. **cookie 名**：`os-access-code` 之外还有 `trim_token` / `fnos-token` 时，",
        "   说明该路由换了一种会话凭据。",
        "4. **状态码**：`/access_code_verify` 回 200 但没有 cookie，说明验证通过、下发条件不满足；",
        "   回 401/403 则是访问码本身被拒。",
        "",
    ]
    return "\n".join(parts)


def report_from_logcat(log_path):
    text = log_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    failures = [line for line in lines if "authentication error" in line or "authentication rejected" in line]
    warnings = [line for line in lines if "FnOsAuth" in line and line not in failures]
    parts = [
        "# fnAudio 登录日志报告",
        "",
        "来源：`%s`" % log_path.name,
        "",
        "- 失败记录：%d 条" % len(failures),
        "- 其它 FnOsAuth 记录：%d 条" % len(warnings),
        "",
    ]
    if failures:
        parts += ["## 失败行", "", "```text"]
        parts += failures[-20:]
        parts += ["```", ""]
    else:
        parts += [
            "> 没有失败记录。如果问题确实发生了，确认抓日志时 App 真的重启过（旧的失败行只在本次缓冲里）。",
            "",
        ]
    if warnings:
        parts += ["## 其它记录", "", "```text"]
        parts += warnings[-20:]
        parts += ["```", ""]
    parts += [
        "## 怎么读",
        "",
        "- `phase=pre-handshake`：还没到 WebSocket 握手，问题在访问码验证或连接建立。",
        "- `phase=handshake`：握手被拒，看 `attempt` 与 `usedPassword`。",
        "- `sessionCookie=absent`：这一轮没拿到会话 cookie（R555 之后不再因此失败）。",
        "- `redirects=N`：访问码验证被重定向了几跳；N>0 说明网关做了跳转。",
        "",
    ]
    return "\n".join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", type=Path, help="mitmdump 文本导出")
    parser.add_argument("--logcat", type=Path, help="adb logcat 文本")
    parser.add_argument("--out", type=Path, required=True, help="输出的 markdown")
    args = parser.parse_args(argv)
    if args.dump:
        markdown = report_from_dump(args.dump)
    elif args.logcat:
        markdown = report_from_logcat(args.logcat)
    else:
        parser.error("需要 --dump 或 --logcat")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown, encoding="utf-8")
    print(markdown.splitlines()[0] + " -> " + str(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
