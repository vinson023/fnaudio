"""从 5.2 上把安装目录里的 app.css 拉回来，与工作区、FPK 里的那份对比。

为什么需要它：浏览器里注入工作区 app.css 后，窄屏播放器从底部跳到顶部并盖住
顶部栏，说明线上那份 CSS 与工作区那份不是一回事。到底是线上旧了，还是工作区
新了，必须拿文件本身比，不能靠表现猜。
"""

from __future__ import annotations

import hashlib
import sys

import paramiko

HOST = "192.168.5.2"
USER = "root"
PASSWORDS = ["vinson520"]

REMOTE_CANDIDATES = [
    "/usr/local/apps/@appcenter/fnaudio/target/ui/app.css",
    "/usr/local/apps/@appcenter/fnaudio/ui/app.css",
    "/var/apps/fnaudio/target/ui/app.css",
]


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    last = None
    for password in PASSWORDS:
        try:
            client.connect(HOST, username=USER, password=password, timeout=10,
                           allow_agent=False, look_for_keys=False)
            break
        except Exception as exc:  # noqa: BLE001
            last = exc
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    else:
        print("connect failed:", last)
        return 1

    for path in REMOTE_CANDIDATES:
        _i, out, _e = client.exec_command(f"ls -l {path} 2>/dev/null; md5sum {path} 2>/dev/null")
        text = out.read().decode().strip()
        if text:
            print(text)

    sftp = client.open_sftp()
    for path in REMOTE_CANDIDATES:
        try:
            data = sftp.open(path, "rb").read()
        except OSError:
            continue
        print(f"fetched {path}: {len(data)} bytes md5={hashlib.md5(data).hexdigest()}")
        with open("/tmp/deployed_app.css", "wb") as handle:
            handle.write(data)
        break
    sftp.close()
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
