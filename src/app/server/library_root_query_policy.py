"""Pure SQL-boundary helpers for configured music-library roots."""

from __future__ import annotations

from typing import Iterable, Tuple

MAX_CONFIGURED_ROOTS = 64


def configured_root_filter(roots: Iterable[str], column: str = "root") -> Tuple[str, list[str]]:
    """Return a bounded ``IN`` predicate and parameters for configured roots.

    The caller already canonicalizes paths, but this helper remains defensive
    so query construction never materializes an unbounded or non-text input.
    """
    if not isinstance(column, str) or not column or len(column) > 64 or not column.replace("_", "").isalnum():
        column = "root"
    values: list[str] = []
    try:
        iterator = iter(roots or ())
    except Exception:
        iterator = iter(())
    for _ in range(MAX_CONFIGURED_ROOTS):
        try:
            value = next(iterator)
        except StopIteration:
            break
        except Exception:
            break
        if not isinstance(value, str) or not value or value in values:
            continue
        values.append(value)
    if not values:
        return "1 = 0", []
    return "%s IN (%s)" % (column, ",".join("?" for _ in values)), values
