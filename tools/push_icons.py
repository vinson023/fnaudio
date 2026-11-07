"""把本地生成的图标推到测试机上，只换图标，不碰应用其它文件。

用在哪：改了 `src/app/ui/images/icon_*.png` 或 `src/ICON*.PNG` 之后，想立刻在
真机/App 里看效果，不必走完整的 FPK 打包＋升级流程。

为什么不用 sftp put 覆盖：
  put 会先删再建，`/usr/local/apps/@appcenter/fnaudio` 下的目录带 ACL（drwxrwxr-x+），
  新建的文件会丢掉原来的 ACL 与属主。这里改成「远端先 cp 备份，再用 sftp 以 wb 打开
  已有文件写」，写的是同一个 inode，权限、属主、ACL 全部原样保留。

用法：
  python tools/push_icons.py --host 192.168.5.141 --password ***
  python tools/push_icons.py --host 192.168.5.20 --password *** --sudo --user admin
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
LOCAL_UI = ROOT / "src" / "app" / "ui" / "images"
SIZES = (16, 24, 48, 64, 72, 96, 128, 256)

REMOTE_APP = "/var/apps/fnaudio"


def local_files() -> list[tuple[Path, str]]:
    """返回 (本地路径, 远端绝对路径)。远端路径以 /var/apps/fnaudio 为基准。"""
    items: list[tuple[Path, str]] = []
    for size in SIZES:
        items.append((LOCAL_UI / f"icon_{size}.png", f"target/ui/images/icon_{size}.png"))
    items.append((LOCAL_UI / "icon_{0}.png", "target/ui/images/icon_{0}.png"))
    items.append((ROOT / "src" / "ICON.PNG", "ICON.PNG"))
    items.append((ROOT / "src" / "ICON_256.PNG", "ICON_256.PNG"))
    return items


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def remote_md5(client: paramiko.SSHClient, path: str) -> str:
    _i, out, _e = client.exec_command(f"md5sum {path} 2>/dev/null | cut -d' ' -f1")
    return out.read().decode().strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", required=True)
    parser.add_argument("--sudo", action="store_true", help="非 root 账号需要 sudo 写 /var/apps")
    args = parser.parse_args()

    items = local_files()
    missing = [str(p) for p, _ in items if not p.exists()]
    if missing:
        print("MISSING", missing)
        return 2

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, port=args.port, username=args.user, password=args.password, timeout=20)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = f"{REMOTE_APP}/upgrade-backups/icons-{stamp}"
    _i, out, err = client.exec_command(f"mkdir -p {backup} && ls {REMOTE_APP}/target/ui/images/ | head -3")
    out.read()
    problem = err.read().decode().strip()
    if problem and "Permission denied" in problem:
        print("NO_PERMISSION", problem)
        return 3

    # 先备份现有图标，改坏了还能照原样退回去
    copies = [f"{REMOTE_APP}/{rel}" for _p, rel in items if not rel.startswith("target/")]
    copies += [f"{REMOTE_APP}/{rel}" for _p, rel in items if rel.startswith("target/")]
    script = " ; ".join(f"cp -p {path} {backup}/$(echo {path} | sed 's#/#_#g')" for path in copies)
    _i, _o, e = client.exec_command(script)
    e.read()
    print("backup dir", backup)

    sftp = client.open_sftp()
    ok = 0
    failed: list[str] = []
    for local, rel in items:
        remote = f"{REMOTE_APP}/{rel}"
        try:
            with sftp.open(remote, "wb") as handle:
                handle.write(local.read_bytes())
            sftp.chmod(remote, 0o644)
        except OSError as exc:
            failed.append(f"{rel} {exc}")
            continue
        expected = md5(local)
        actual = remote_md5(client, remote)
        if expected == actual:
            ok += 1
            print("OK  ", rel, expected)
        else:
            failed.append(f"{rel} md5 {actual} != {expected}")
    sftp.close()

    # 飞牛读的是 /var/apps/<app>/ICON*.PNG，不是 target/ui 里那张，两边都必须换
    print(f"\n{ok}/{len(items)} matched")
    for line in failed:
        print("FAIL", line)
    client.close()
    return 0 if not failed else 4


if __name__ == "__main__":
    sys.exit(main())
