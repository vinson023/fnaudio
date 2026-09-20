"""Pure construction of a scanned CUE track record."""


def build_cue_item(item_id, metadata, ext, mime, is_dsd, size, audio_info,
                   path, cue_path, cue_track, cue_start, cue_end,
                   scan_started, modified, modified_ns, metadata_version):
    # A cue_end of 0.0 means "the scan knows no boundary for this segment", not
    # "the segment ends at zero", so an unknown boundary presents as a zero-length
    # track instead of one that fills the source file.
    duration = max(0.0, cue_end - cue_start) if cue_end > cue_start else 0.0
    return {
        "id": item_id,
        **metadata,
        "format": ext[1:].upper(),
        "mime": mime,
        "is_dsd": bool(is_dsd),
        "size": size,
        **audio_info,
        "duration": duration,
        "path": path,
        "cue_path": cue_path,
        "cue_track": bool(cue_track),
        "cue_start": cue_start,
        "cue_end": cue_end,
        "added": int(scan_started),
        "added_ns": int(scan_started * 1000000000),
        "modified": int(modified),
        "modified_ns": modified_ns,
        "metadata_version": metadata_version,
    }
