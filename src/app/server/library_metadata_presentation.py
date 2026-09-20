"""Pure library-facing metadata presentation rules for scanned audio files."""

from __future__ import annotations

from metadata_text import artist_title_from_filename, clean_tag, display_name, parse_track_number


def library_metadata(path, tags, folder, library_root, unclassified="未分类"):
    """Build a scan record from already-read tags and path presentation values."""
    source = dict(tags) if isinstance(tags, dict) else {}
    tag_title = clean_tag(source.get("title"))
    tag_artist = clean_tag(source.get("artist"))
    filename_artist, filename_title = artist_title_from_filename(path)
    return {
        "title": tag_title or filename_title or display_name(path),
        "artist": tag_artist or filename_artist or "未知艺术家",
        "album": clean_tag(source.get("album")) or unclassified,
        "composer": clean_tag(source.get("composer")) or "未知作曲者",
        "genre": clean_tag(source.get("genre")) or "未分类",
        "track_no": parse_track_number(source.get("track_no")),
        "folder": folder if isinstance(folder, str) else "",
        "library_root": library_root if isinstance(library_root, str) else "",
        "metadata_source": {
            "title": "tag" if tag_title else "filename",
            "artist": "tag" if tag_artist else ("filename" if filename_artist else "unknown"),
            "album": "tag" if clean_tag(source.get("album")) else "unknown",
        },
    }
