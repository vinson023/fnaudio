"""Pure presentation rules for the library status endpoint."""

from __future__ import annotations


def status_message(status):
    """Return the user-facing message for an already-probed status mapping."""
    if not status.get("allowed"):
        return "出于安全保护，这个路径不能作为音乐目录"
    if not status.get("exists"):
        return "音乐目录不存在，请在应用设置里选择正确的音乐文件夹"
    if not status.get("is_dir"):
        return "音乐路径不是文件夹"
    if not status.get("readable"):
        return "应用没有权限读取这个音乐文件夹"
    if status.get("scanning") and not status.get("count"):
        return "正在扫描音乐目录"
    return "音乐库已就绪" if status.get("count") else "没有在这个目录里找到支持的音乐文件"


__all__ = ["status_message"]
