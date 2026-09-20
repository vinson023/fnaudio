"""Bounded rowid candidate generation for large unfiltered random pages."""


MAX_RANDOM_ROWID_CANDIDATES = 400


def random_rowid_candidates(maximum, size, randrange):
    """Return a bounded, deduplicated set of one-based SQLite rowid guesses."""
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
        return []
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        return []
    if not callable(randrange):
        return []
    target = min(MAX_RANDOM_ROWID_CANDIDATES, max(1, size))
    values = set()
    for _ in range(target):
        try:
            value = randrange(1, maximum + 1)
        except Exception:
            break
        if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= maximum:
            values.add(value)
    return sorted(values)
