"""Safe resolution of an indexed item to a file-manager location."""

import os
from collections.abc import Mapping


def resolve_item_location(item, requested_id, roots, path_under, max_text=4096):
    """Return a canonical file location only when it stays under a root."""
    if not isinstance(item, Mapping) or not callable(path_under):
        return None
    raw_path = item.get("path")
    if not isinstance(raw_path, str) or len(raw_path) > max_text:
        return None
    raw_path = raw_path.strip()
    if not raw_path:
        return None
    try:
        real_path = os.path.realpath(os.path.abspath(os.path.expanduser(raw_path)))
        root_values = []
        for root in roots or ():
            if isinstance(root, str) and len(root) <= max_text:
                root_values.append(os.path.realpath(os.path.abspath(root)))
    except Exception:
        return None
    try:
        valid = os.path.isfile(real_path) and any(path_under(real_path, root) for root in root_values)
    except Exception:
        valid = False
    if not valid:
        return None
    item_id = item.get("id") if isinstance(item.get("id"), str) else (requested_id if isinstance(requested_id, str) else "")
    return {"id": item_id, "path": real_path, "folder": os.path.dirname(real_path)}


__all__ = ["resolve_item_location"]
