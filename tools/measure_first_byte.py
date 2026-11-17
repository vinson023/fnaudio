# -*- coding: utf-8 -*-
"""首帧延迟的可重复测量（P1）。

本机（Windows 开发机）通常没有 ffmpeg，而真正转码的是 NAS，所以测量在测试机上做：
用 SSH 起一条与 `transcode.py::transcode_command` **同一份参数**的命令，量"到首字节"
的毫秒数，带 / 不带探测参数各跑若干次，报中位数并与基线比较。

用法::

    python tools/measure_first_byte.py                 # 测量 + 与基线比较
    python tools/measure_first_byte.py --update         # 把本次结果写成新基线
    python tools/measure_first_byte.py --runs 7         # 取样次数（默认 5）

退出码 1 表示相对基线明显变慢（默认阈值：中位数超过基线 1.5 倍且多 30ms 以上）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "_external" / "pyssh"))
sys.path.insert(0, str(REPO / "src" / "app" / "server"))

DEFAULT_HOST = "192.168.5.141"
DEFAULT_USER = "root"
DEFAULT_PASSWORD = "vinson520"
BASELINE = REPO / "docs" / "perf" / "baseline_first_byte.json"
SAMPLE = "/tmp/fnaudio-probe-sample.flac"


def _transcode_args() -> list[str]:
    """用产品代码生成参数，避免脚本和实现各写一份。"""
    from unittest import mock

    import transcode

    with mock.patch.object(transcode, "find_ffmpeg", return_value="ffmpeg"):
        command, _mime, _env = transcode.transcode_command({"path": SAMPLE}, {}, "mp3")
    return command[1:]  # 去掉 ffmpeg 自身


def _connect(host: str, user: str, password: str):
    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=22, username=user, password=password, timeout=10)
    return client


def _run(client, command: str, timeout: int = 120) -> tuple[str, str]:
    _in, out, err = client.exec_command(command, timeout=timeout)
    return out.read().decode("utf-8", "replace"), err.read().decode("utf-8", "replace")


def _ensure_sample(client) -> str:
    out, _ = _run(client, "command -v ffmpeg >/dev/null && echo ok || echo missing")
    if "ok" not in out:
        raise SystemExit("测试机上没有 ffmpeg")
    _run(client, "test -f %s || ffmpeg -hide_banner -loglevel error -f lavfi "
                 "-i sine=frequency=440:duration=30 -c:a flac %s" % (SAMPLE, SAMPLE), timeout=180)
    return SAMPLE


def _measure(client, args: list[str], runs: int) -> list[float]:
    quoted = " ".join("'%s'" % a.replace("'", "'\\''") for a in args)
    # 只读到第一个字节就断开：这正是"首帧"的定义。
    # 不用 %-格式化：`date +%s%N` 里的 %s 会被当成占位符。
    template = (
        "s=$(date +%s%N); ffmpeg __ARGS__ 2>/dev/null | head -c 1 >/dev/null; "
        "e=$(date +%s%N); echo $(( (e - s) / 1000000 ))"
    )
    samples = []
    for _ in range(runs):
        out, err = _run(client, template.replace("__ARGS__", quoted))
        value = out.strip().splitlines()[-1] if out.strip() else ""
        if not value.isdigit():
            raise SystemExit("测量失败: %s %s" % (out.strip()[:120], err.strip()[:120]))
        samples.append(float(value))
    return samples


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--update", action="store_true", help="把结果写成新基线")
    parser.add_argument("--tolerance", type=float, default=1.5)
    parser.add_argument("--floor-ms", type=float, default=30.0)
    args = parser.parse_args()

    command_args = _transcode_args()

    client = _connect(args.host, args.user, args.password)
    try:
        _ensure_sample(client)
        for _ in range(2):  # 预热，避免首次页面缓存算进样本
            _measure(client, command_args, 1)
        samples = _measure(client, command_args, args.runs)
    finally:
        client.close()

    median_ms = statistics.median(samples)
    result = {
        "host": args.host,
        "measure": "转码到首个字节的毫秒数（中位数，含进程启动）",
        "runs": args.runs,
        "median_ms": median_ms,
        "samples": samples,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.update:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("已写入基线:", BASELINE.relative_to(REPO))
        return 0

    if not BASELINE.is_file():
        print("没有基线，先用 --update 建立一次（这份输出即可作为基线）")
        return 0

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    base = baseline.get("median_ms", 0)
    limit = base * args.tolerance + args.floor_ms
    if median_ms > limit:
        print("回归：当前 %.0fms 超过基线 %.0fms 的允许上限 %.0fms" % (median_ms, base, limit))
        return 1
    print("在基线范围内（当前 %.0fms，基线 %.0fms，上限 %.0fms）" % (median_ms, base, limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
