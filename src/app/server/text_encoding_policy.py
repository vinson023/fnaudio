"""Pick the most plausible text encoding for a CUE sheet or a .lrc file.

R591 replaced the old fallback chain ``utf-8-sig -> gb18030 -> big5 -> latin1``.
That chain could not work: ``gb18030`` accepts almost every byte pair, so it never
raised, ``big5`` was therefore unreachable, and ``latin1`` accepts *everything* --
which is why a Big5 sheet's 「晴天」 came out as 「锤ぱ」 with no error anywhere.

There is no deterministic way to tell GBK from Big5 from Shift-JIS by looking at
bytes alone; that is why every player that gets it right asks the user or ships a
statistical model.  This module therefore does three things instead of pretending:

* **BOM first.**  A UTF-16 or UTF-8 byte-order mark is an explicit statement.
* **UTF-8 strict next.**  A byte sequence that decodes as strict UTF-8 is
  almost certainly UTF-8, so a successful decode settles it.
* **The configured encoding next.**  ``text_encoding`` in the library config is
  the deterministic answer for a library that is entirely Big5 or entirely
  Shift-JIS.  Auto-detection is a heuristic and is documented as one.

Only when none of those applies does the heuristic run: decode with each legacy
candidate and score the *result*, because a wrong decoding produces text that
looks wrong -- half-width katakana next to Chinese, private-use glyphs, control
characters, or ideographs from the rare extension blocks.  The two marker sets
below carry the script signal: a Big5 sheet that contains 「倫」「樂」 is Big5,
and a GBK sheet that contains 「这」「时」 is GBK.
"""

from __future__ import annotations

# Ordered so that a tie falls to the earlier candidate.  utf-8 is tried on its
# own first (see decode_text); this tuple is the legacy set the scorer ranks.
LEGACY_CANDIDATES = ("gb18030", "big5", "shift_jis")

# The user-facing setting accepts the names people actually type.
EXPLICIT_ALIASES = {
    "utf-8": "utf-8-sig",
    "utf8": "utf-8-sig",
    "utf-8-sig": "utf-8-sig",
    "utf8-sig": "utf-8-sig",
    "utf-16": "utf-16",
    "utf16": "utf-16",
    "gb18030": "gb18030",
    "gbk": "gb18030",
    "gb2312": "gb18030",
    "cp936": "gb18030",
    "big5": "big5",
    "big-5": "big5",
    "cp950": "big5",
    "shift_jis": "shift_jis",
    "shift-jis": "shift_jis",
    "sjis": "shift_jis",
    "cp932": "shift_jis",
}

# High-frequency characters that exist in only one of the two Chinese scripts.
# Kept deliberately short: these are markers, not a language model, and every
# extra entry is another way for a legitimate file to be scored down.
SIMPLIFIED_ONLY = frozenset(
    "这个说时们来对开关无发经过还进种样么为国动产业实点后东车门问间见让认识语请谢岁书学觉"
    "头长门问题题应该经给带当里听写读买卖钱银铁铜钟钱馆饭菜汤鱼肉鸡鸭猪马鸟龙龟"
)
TRADITIONAL_ONLY = frozenset(
    "這個說時們來對開關無發經過還進種樣麼為國動產業實點後東車門問間見讓認識語請謝歲書學覺"
    "頭長門問題題應該經給帶當裡聽寫讀買賣錢銀鐵銅鐘錢館飯菜湯魚肉雞鴨豬馬鳥龍龜"
)

MAX_SCORE_TEXT = 200000


def normalize_encoding_setting(value):
    """Return the canonical encoding for a config value, or "" for auto.

    An unknown name is treated as "auto" rather than raising: a typo in a config
    file must not stop the library from scanning.
    """
    if not isinstance(value, str):
        return ""
    return EXPLICIT_ALIASES.get(value.strip().lower().replace(" ", ""), "")


def _has_utf16_bom(payload):
    return payload[:2] in (b"\xff\xfe", b"\xfe\xff")


def _score(text, encoding):
    """How plausible does ``text`` look, given it was decoded as ``encoding``?"""
    cjk = kana = halfwidth = private = control = rare = 0
    marker = 0
    traditional = encoding == "big5"
    for char in text[:MAX_SCORE_TEXT]:
        point = ord(char)
        if 0x4E00 <= point <= 0x9FFF:
            cjk += 1
        elif 0x3040 <= point <= 0x30FF:
            kana += 1
        elif 0xFF61 <= point <= 0xFF9F:
            # Half-width katakana in a Chinese sheet is the classic
            # "decoded the wrong way" artefact.
            halfwidth += 1
        elif 0xE000 <= point <= 0xF8FF:
            private += 1
        elif 0x3400 <= point <= 0x4DBF or point >= 0x20000:
            rare += 1
        elif point < 32 and char not in "\t\n\r":
            control += 1
        if traditional:
            if char in TRADITIONAL_ONLY:
                marker += 1
        elif char in SIMPLIFIED_ONLY:
            marker += 1
    return (2 * cjk) + (3 * kana) + (4 * marker) - (4 * halfwidth) - (6 * private) - (8 * control) - (2 * rare)


def decode_text(payload, explicit=""):
    """Decode ``payload`` and say which encoding was used.

    Returns ``(text, encoding)``; ``(None, "")`` when no candidate decodes it at
    all.  ``explicit`` is the configured ``text_encoding`` -- it wins over the
    heuristic but not over a byte-order mark or over a byte sequence that is
    valid strict UTF-8, because both of those are stronger evidence than a
    setting that may have been chosen for a different library.
    """
    if not isinstance(payload, (bytes, bytearray)) or not payload:
        return None, ""
    payload = bytes(payload)
    if _has_utf16_bom(payload):
        try:
            return payload.decode("utf-16"), "utf-16"
        except UnicodeError:
            return None, ""
    try:
        return payload.decode("utf-8-sig"), "utf-8-sig"
    except UnicodeError:
        pass
    chosen = normalize_encoding_setting(explicit)
    if chosen and chosen != "utf-8-sig":
        try:
            text = payload.decode(chosen)
        except UnicodeError:
            # A setting that cannot decode this file must not mask the file.
            text = None
        if text is not None and _score(text, chosen) >= 0:
            # The setting is honoured unless it produces text that looks like
            # nothing at all -- half-width katakana where a Chinese title should
            # be, control characters, private-use glyphs.  Overriding a *plausible*
            # explicit choice with a heuristic would make the setting useless in
            # exactly the cases it exists for (a two-character title carries no
            # script marker, so the scorer cannot separate GBK from Big5 there).
            return text, chosen
    best_text, best_encoding, best_score = None, "", None
    for encoding in LEGACY_CANDIDATES:
        try:
            text = payload.decode(encoding)
        except UnicodeError:
            continue
        score = _score(text, encoding)
        if best_score is None or score > best_score:
            best_text, best_encoding, best_score = text, encoding, score
    if best_text is None:
        return None, ""
    return best_text, best_encoding


def decode_lines(payload, explicit=""):
    """Decode to a list of lines, keeping the CR/LF handling the callers had."""
    text, _encoding = decode_text(payload, explicit)
    if text is None:
        return []
    return text.splitlines()


__all__ = [
    "EXPLICIT_ALIASES",
    "LEGACY_CANDIDATES",
    "SIMPLIFIED_ONLY",
    "TRADITIONAL_ONLY",
    "decode_lines",
    "decode_text",
    "normalize_encoding_setting",
]
