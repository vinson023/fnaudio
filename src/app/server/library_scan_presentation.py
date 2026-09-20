"""Pure builders for scan results.

Keeping record construction separate from filesystem walking makes the scan
loop easier to test without touching the filesystem or ffprobe.
"""


def build_audio_item(item_id, metadata, ext, mime, is_dsd, size, audio_info,
                     path, scan_started, stat, metadata_version=16):
    """Return the stable library record for a regular audio file."""
    return {
        "id": item_id,
        **metadata,
        "format": ext[1:].upper(),
        "mime": mime,
        "is_dsd": bool(is_dsd),
        "size": size,
        "duration": 0,
        **audio_info,
        "path": path,
        "added": int(scan_started),
        "added_ns": int(scan_started * 1000000000),
        "modified": int(stat.st_mtime),
        "modified_ns": stat.st_mtime_ns,
        "metadata_version": metadata_version,
    }
