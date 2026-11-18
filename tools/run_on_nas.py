"""在飞牛主机上跑一段 python，按需上传本地脚本再执行。

    py -3 tools/run_on_nas.py <local_py_file> [--py /var/apps/python312/target/bin/python3]
    py -3 tools/run_on_nas.py <local_py_file> --put src/app/server/library_paths.py=/tmp/x/library_paths.py

用 SFTP 上传再执行，避免把 heredoc 塞进 ``bash -s`` 的 stdin ——
脚本本身走 stdin 时 bash 会把 heredoc 的内容一起吞掉，python 就一直等输入。
"""

import argparse
import posixpath
import sys
import uuid

import paramiko

HOST = "192.168.5.141"
PASSWORD = "vinson520"
DEFAULT_PY = "/var/apps/python312/target/bin/python3"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("script")
    parser.add_argument("--py", default=DEFAULT_PY)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument(
        "--put",
        action="append",
        default=[],
        metavar="LOCAL=REMOTE",
        help="先上传这个本地文件到远端路径，可重复",
    )
    args = parser.parse_args()

    remote = posixpath.join("/tmp", "fnaudio-diag-%s.py" % uuid.uuid4().hex[:8])
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username="root", password=PASSWORD, timeout=20)
    try:
        sftp = client.open_sftp()
        for pair in args.put:
            local, _, target = pair.partition("=")
            parent = posixpath.dirname(target)
            if parent:
                client.exec_command("mkdir -p %s" % parent)[1].channel.recv_exit_status()
            sftp.put(local, target)
        sftp.put(args.script, remote)
        sftp.close()
        command = "%s -u %s 2>&1" % (args.py, remote)
        _, stdout, stderr = client.exec_command(command, timeout=args.timeout)
        for line in stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
        tail = stderr.read().decode("utf-8", "replace")
        if tail.strip():
            sys.stdout.write("\n--- stderr ---\n" + tail)
    finally:
        client.exec_command("rm -f %s" % remote)
        client.close()


if __name__ == "__main__":
    main()
