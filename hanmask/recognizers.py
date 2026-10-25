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
    # Keywords shortly before a match, in the same clause, are checked in
    # order: `context` (統編) keeps it; `require_context` drops it when no
    # such keyword is present; `exclude` (訂單, 料號) drops it. Otherwise the
    # pattern and checksum decide. Order matters: 統一編號 contains 編號.
    context: re.Pattern[str] | None = None
    require_context: bool = False
    exclude: re.Pattern[str] | None = None

    def _keep(self, normalized: str, start: int) -> bool:
        if self.context is not None and _has_context(self.context, normalized, start):
            return True
        if self.require_context:
            return False
        return self.exclude is None or not _has_context(self.exclude, normalized, start)

    def find(self, text: str, normalized: str | None = None) -> Iterable[Entity]:
        """Match against the normalized text; report the original characters."""
        normalized = normalize(text) if normalized is None else normalized
        # A pattern with a group named "v" masks only that group; the rest is
        # the label that anchors it (訂單編號：).
        group = "v" if "v" in self.pattern.groupindex else 0
        for m in self.pattern.finditer(normalized):
            start, end = m.span(group)
            if not self._keep(normalized, start):
                continue
            if self.validate is None or self.validate(m.group(group)):
                yield Entity(self.type, start, end, text[start:end])


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

# Labels for internal identifiers that share a format with real PII: an
# 8-digit order number passes the UBN checksum one time in five. PII
# recognizers skip values under these labels; the business recognizers
# below mask them under their own types.
_ID_LIKE = re.compile(r"訂單|單號|編號|序號|料號|代碼|案號|批號|發票|order|invoice|sku", re.IGNORECASE)

# Business identifier: label, optional 編號/號碼/No., separators, then a
# value of 5+ characters with at least one digit (PO-2024-00123, 04595257).
_BIZ_VALUE = r"(?P<v>(?=[A-Za-z0-9-]{5,})(?=[A-Za-z-]*\d)[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)" + _R


def _labelled(entity_type: str, labels: str, sep: str, value: str, priority: int) -> Recognizer:
    """A value masked only when its label sits right before it; `value` holds group "v"."""
    return Recognizer(
        entity_type,
        re.compile(r"(?<![A-Za-z])(?:" + labels + r")" + sep + value, re.IGNORECASE),
        priority=priority,
    )


def _business(entity_type: str, labels: str, priority: int) -> Recognizer:
    # Lowest priorities: on an identical span a PII type that passed its own
    # checks is the better label (身分證編號 A123456789 is a TW_ID).
    return _labelled(entity_type, labels, r" ?(?:編號|號碼|號|no\.?|number)?[ :#]*", _BIZ_VALUE, priority)


_CJK = r"[一-鿿]"
_CN_NUM = r"(?:\d+|[一二三四五六七八九十]+)"
_CITY = (
    r"(?:臺北|台北|新北|桃園|臺中|台中|臺南|台南|高雄|基隆|新竹|嘉義|苗栗|彰化"
    r"|南投|雲林|屏東|宜蘭|花蓮|臺東|台東|澎湖|金門|連江)[市縣]"
)

# Postal code, city and/or district, village, road, section, lane, alley,
# number, floor. A road and a house number are required, so 台北市大安區
# alone stays unmasked.
_ADDRESS = re.compile(
    r"(?P<v>(?:\d{3}(?:\d{2,3})? ?)?"
    r"(?:" + _CITY + r"(?:" + _CJK + r"{1,3}?[區鄉鎮市])?|" + _CJK + r"{1,3}?[區鄉鎮])"
    r"(?:" + _CJK + r"{1,3}?[里村])?(?: ?\d+ ?鄰)?"
    r" ?" + _CJK + r"{1,6}?(?:路|街|大道)"
    r"(?: ?" + _CN_NUM + r" ?段)?(?: ?\d+ ?巷)?(?: ?\d+ ?弄)?"
    r" ?\d+(?:[-之]\d+)? ?號"
    r"(?: ?" + _CN_NUM + r" ?樓(?:之 ?\d+)?)?(?: ?\d+ ?室)?)"
)

# Company names by legal suffix. A short particle before the name (給, 與,
# 戶名) is left outside the masked span. Names with no suffix wait for NER.
_ORG_PARTICLES = r"給|向|與|跟|和|及|由|於|在|是|為|的|至|到|戶名|客戶|廠商|供應商|委託"
_ORG_ZH = re.compile(
    r"(?:" + _CJK + r"*?(?:" + _ORG_PARTICLES + r"))?"
    r"(?P<v>[一-鿿A-Za-z0-9]{2,12}?(?:(?:股份)?有限公司|企業社|商行|工作室|事務所))"
)
_ORG_EN = re.compile(
    r"(?<![A-Za-z])(?P<v>[A-Z][A-Za-z0-9&]*(?: [A-Z][A-Za-z0-9&]*){0,4},? "
    r"(?:Co\., ?Ltd\.?|Inc\.?|Ltd\.?|Corp(?:oration)?\.?|LLC|GmbH))"
)

_DATE = (
    r"(?P<v>(?:民國 ?)?\d{2,4} ?[/.\-年] ?\d{1,2} ?[/.\-月] ?\d{1,2}(?: ?日)?)(?!\d)"
)
_SALARY = (
    r"(?P<v>(?:(?:NT\$|NTD|新台幣|台幣|\$) ?)?"
    r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?(?: ?[萬千kK])?|\d+(?:\.\d+)? ?[萬千kK]|\d{4,}))(?!\d)"
)

BUSINESS_TYPES = frozenset({"ORDER_NO", "INVOICE_NO", "PART_NO", "REF_NO", "ORG_NAME"})

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
        context=re.compile(r"身分證|身份證|居留證|統一證號"),
        exclude=_ID_LIKE,
    ),
    # No checksum for these three, so each needs a keyword nearby. They outrank
    # CREDIT_CARD and PHONE: "帳號 0912345678" is an account, not a phone.
    Recognizer(
        "PASSPORT",
        re.compile(_L + r"[A-Za-z]{0,2}\d{7,9}" + _R),
        priority=35,
        context=re.compile(r"護照|passport", re.IGNORECASE),
        require_context=True,
    ),
    Recognizer(
        "TW_NHI",
        re.compile(_L + r"\d{4}[ -]?\d{4}[ -]?\d{4}" + _R),
        priority=35,
        context=re.compile(r"健保"),
        require_context=True,
    ),
    Recognizer(
        "BANK_ACCOUNT",
        re.compile(_L + r"\d(?:[ -]?\d){9,15}" + _R),
        priority=35,
        context=re.compile(r"帳號|帳戶|戶頭|匯款|轉帳|account|acct", re.IGNORECASE),
        require_context=True,
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
        context=re.compile(r"電話|手機|市話|傳真|專線|tel|phone|mobile|fax", re.IGNORECASE),
        exclude=_ID_LIKE,
    ),
    Recognizer(
        "TW_UBN",
        re.compile(_L + r"\d{8}" + _R),
        is_valid_tw_ubn,
        priority=10,
        context=re.compile(r"統編|統一編號|營利事業|稅籍"),
        exclude=_ID_LIKE,
    ),
    Recognizer("ADDRESS", _ADDRESS, priority=45),
    Recognizer(
        "IP_ADDRESS",
        re.compile(
            r"(?<![\d.A-Za-z])(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?!\d|\.\d)"
        ),
        priority=40,
        exclude=re.compile(r"版本|版號|version", re.IGNORECASE),
    ),
    Recognizer(
        "UUID",
        re.compile(_L + r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}" + _R),
        priority=40,
    ),
    # "LINE" alone is too common (LINE Pay, LINE 群組): require ID/帳號 or a colon.
    Recognizer(
        "SOCIAL_ID",
        re.compile(
            r"(?<![A-Za-z])(?:line|ig|instagram|telegram|wechat|微信)(?: ?(?:id|帳號)(?: ?:)?| ?:) *"
            r"(?P<v>@?[A-Za-z0-9][A-Za-z0-9._-]{2,18}[A-Za-z0-9])(?![A-Za-z0-9_-])",
            re.IGNORECASE,
        ),
        priority=30,
    ),
    _labelled(
        "BIRTH_DATE",
        r"生日|出生日期|出生年月日|出生|生於|birthday|birth ?date|date of birth|dob",
        r"(?:日期|為|是|[ :])*",
        _DATE,
        30,
    ),
    # Salary only: other amounts (invoices, receivables) stay visible so an
    # LLM can still reason about them.
    _labelled(
        "SALARY",
        r"月薪|年薪|薪資|薪水|底薪|本薪|時薪|日薪|起薪|調薪|獎金|年終|津貼|加給|salary|bonus",
        r"(?:調整為|調至|為|是|約|共|[ :])*",
        _SALARY,
        8,
    ),
    Recognizer("ORG_NAME", _ORG_ZH, priority=6),
    Recognizer("ORG_NAME", _ORG_EN, priority=6),
    _business("ORDER_NO", r"訂單|採購單|出貨單|報價單|單號|order", 5),
    _business("INVOICE_NO", r"發票|invoice", 5),
    _business("PART_NO", r"料號|品號|sku|part", 5),
    _business("REF_NO", r"(?<!統一)編號|序號|流水號|案號|批號|代碼|合約|證號|字號", 4),
)

PII_TYPES = frozenset(r.type for r in DEFAULT_RECOGNIZERS) - BUSINESS_TYPES


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
