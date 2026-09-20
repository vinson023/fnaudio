"""Pure SQL policy for library group labels."""

UNCLASSIFIED = "未分类"
GROUP_COLUMNS = frozenset(("album", "artist", "composer", "genre"))
MAX_GROUP_VALUE_TEXT = 4096


def group_match_condition(column, value):
    column = column if isinstance(column, str) else ""
    plain_column = column[2:] if column.startswith("t.") else column
    if plain_column not in GROUP_COLUMNS:
        raise ValueError("unsupported library group column")
    value = value[:MAX_GROUP_VALUE_TEXT] if isinstance(value, str) else ""
    if value == UNCLASSIFIED:
        return "(%s = ? OR %s = '' OR %s IS NULL)" % (column, column, column), [UNCLASSIFIED]
    return "%s = ?" % column, [value]
