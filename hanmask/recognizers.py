"""Rule-based PII recognizers: regular expressions plus checksum validation.

Each recognizer finds candidate spans with a regex and, where the format has
one, confirms them with a checksum so random digit runs are not masked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable

# Python's \b treats CJK characters as word characters, so "統編12345675"
# has no boundary before the digits. Use explicit ASCII lookarounds instead.
_L = r"(?<![0-9A-Za-z])"
_R = r"(?![0-9A-Za-z])"

# Traditional Chinese text often types numbers and IDs in full-width form
# (０９１２－３４５－６７８, Ａ１２３４５６７８９, （０２）). Map full-width ASCII
# and the ideographic space to ASCII one character for one character, so
# offsets in the normalized text are offsets in the original.
_FULLWIDTH = {cp: cp - 0xFEE0 for cp in range(0xFF01, 0xFF5F)}
_FULLWIDTH[0x3000] = 0x20


def normalize(text: str) -> str:
    """Full-width to half-width, length-preserving."""
    return text.translate(_FULLWIDTH)


# How far back a context keyword may sit, and where a clause ends: in
# "帳號 jay，電話 0912345678" the keyword belongs to the first clause only.
# Full-width ， and ； are already ASCII after normalize().
_CONTEXT_WINDOW = 20
_CLAUSE_BREAK = re.compile(r"[,;。、\n]")


def _has_context(context: re.Pattern[str], normalized: str, start: int) -> bool:
    before = normalized[max(0, start - _CONTEXT_WINDOW):start]
    return context.search(_CLAUSE_BREAK.split(before)[-1]) is not None


@dataclass(frozen=True)
class Entity:
    type: str
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Recognizer:
    type: str
    pattern: re.Pattern[str]
    validate: Callable[[str], bool] | None = None
    # Higher wins when two matches overlap with the same length.
    priority: int = 0
    # Formats with no checksum (plain digit runs) only count when a keyword
    # such as 護照 or 帳號 appears shortly before them, in the same clause.
    context: re.Pattern[str] | None = None

    def find(self, text: str, normalized: str | None = None) -> Iterable[Entity]:
        """Match against the normalized text; report the original characters."""
        normalized = normalize(text) if normalized is None else normalized
        for m in self.pattern.finditer(normalized):
            if self.context is not None and not _has_context(self.context, normalized, m.start()):
                continue
            if self.validate is None or self.validate(m.group(0)):
                yield Entity(self.type, m.start(), m.end(), text[m.start():m.end()])


# --- Taiwan national ID / resident certificate -------------------------------

_TW_LETTER_CODES = {
    "A": 10, "B": 11, "C": 12, "D": 13, "E": 14, "F": 15, "G": 16, "H": 17,
    "I": 34, "J": 18, "K": 19, "L": 20, "M": 21, "N": 22, "O": 35, "P": 23,
    "Q": 24, "R": 25, "S": 26, "T": 27, "U": 28, "V": 29, "W": 32, "X": 30,
    "Y": 31, "Z": 33,
}
_TW_ID_WEIGHTS = (1, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1)


def is_valid_tw_id(value: str) -> bool:
    """National ID (A123456789) or resident certificate.

    Resident certificates come in the new style (A800000014, since 2021) and
    the old style (AB12345677), still valid on cards issued before then; in
    the old style the second letter counts as the last digit of its code.
    """
    value = normalize(value).upper()
    if not re.fullmatch(r"[A-Z][1289A-D]\d{8}", value):
        return False
    code = _TW_LETTER_CODES[value[0]]
    second = _TW_LETTER_CODES[value[1]] % 10 if value[1].isalpha() else int(value[1])
    digits = [code // 10, code % 10, second] + [int(c) for c in value[2:]]
    return sum(d * w for d, w in zip(digits, _TW_ID_WEIGHTS)) % 10 == 0


# --- Taiwan unified business number (統一編號) --------------------------------

_UBN_WEIGHTS = (1, 2, 1, 2, 1, 2, 4, 1)


def is_valid_tw_ubn(value: str) -> bool:
    """Checksum per the Ministry of Finance rule (divisible by 5 since 2023)."""
    if not re.fullmatch(r"\d{8}", value):
        return False
    total = 0
    for c, w in zip(value, _UBN_WEIGHTS):
        p = int(c) * w
        total += p // 10 + p % 10
    if total % 5 == 0:
        return True
    # When the 7th digit is 7, its product 28 may count as either 10 or 1.
    return value[6] == "7" and (total + 1) % 5 == 0


# --- Credit card ------------------------------------------------------------


def is_valid_luhn(value: str) -> bool:
    digits = [int(c) for c in value if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# --- Registry ---------------------------------------------------------------

DEFAULT_RECOGNIZERS: tuple[Recognizer, ...] = (
    Recognizer(
        "EMAIL",
        re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}" + _R),
        priority=50,
    ),
    Recognizer(
        "TW_ID",
        re.compile(_L + r"[A-Za-z][1289A-Da-d]\d{8}" + _R),
        is_valid_tw_id,
        priority=40,
    ),
    # No checksum for these three, so each needs a keyword nearby. They outrank
    # CREDIT_CARD and PHONE: "帳號 0912345678" is an account, not a phone.
    Recognizer(
        "PASSPORT",
        re.compile(_L + r"[A-Za-z]{0,2}\d{7,9}" + _R),
        priority=35,
        context=re.compile(r"護照|passport", re.IGNORECASE),
    ),
    Recognizer(
        "TW_NHI",
        re.compile(_L + r"\d{4}[ -]?\d{4}[ -]?\d{4}" + _R),
        priority=35,
        context=re.compile(r"健保"),
    ),
    Recognizer(
        "BANK_ACCOUNT",
        re.compile(_L + r"\d(?:[ -]?\d){9,15}" + _R),
        priority=35,
        context=re.compile(r"帳號|帳戶|戶頭|匯款|轉帳|account|acct", re.IGNORECASE),
    ),
    Recognizer(
        "CREDIT_CARD",
        re.compile(_L + r"\d(?:[ -]?\d){12,18}" + _R),
        is_valid_luhn,
        priority=30,
    ),
    Recognizer(
        "PHONE",
        re.compile(
            _L
            + r"(?:"
            # Mobile: 0912-345-678, 0912345678, +886 912 345 678
            + r"(?:\+886[ -]?|0)9\d{2}[ -]?\d{3}[ -]?\d{3}"
            + r"|"
            # Landline: 02-2345-6789, (02)2345-6789, 07-123-4567, +886-2-2345-6789
            + r"(?:\+886[ -]?|0|\(0)[2-8]\)?[ -]?\d{3,4}[ -]?\d{4}"
            + r")"
            + _R
        ),
        priority=20,
    ),
    Recognizer(
        "TW_UBN",
        re.compile(_L + r"\d{8}" + _R),
        is_valid_tw_ubn,
        priority=10,
    ),
)


def find_entities(
    text: str,
    recognizers: Iterable[Recognizer] = DEFAULT_RECOGNIZERS,
    enabled: set[str] | None = None,
) -> list[Entity]:
    """Return non-overlapping entities, sorted by position.

    Overlaps are resolved greedily: longer matches first, then by priority.
    """
    normalized = normalize(text)
    candidates: list[tuple[Entity, int]] = []
    for r in recognizers:
        if enabled is not None and r.type not in enabled:
            continue
        candidates.extend((e, r.priority) for e in r.find(text, normalized))

    candidates.sort(key=lambda c: (-(c[0].end - c[0].start), -c[1], c[0].start))
    chosen: list[Entity] = []
    for entity, _ in candidates:
        if all(entity.end <= c.start or entity.start >= c.end for c in chosen):
            chosen.append(entity)
    return sorted(chosen, key=lambda e: e.start)
