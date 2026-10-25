"""Special categories of personal data (個資法第 6 條).

Medical records, health checks, genetics, sex life and criminal records
cannot be masked reliably: a diagnosis is free text, not a format. In strict
mode a request that mentions them is blocked instead of forwarded.
"""

from __future__ import annotations

import re

from .recognizers import normalize

SENSITIVE_CATEGORIES: dict[str, re.Pattern[str]] = {
    "MEDICAL": re.compile(
        r"診斷|病歷|病史|就醫|就診|回診|門診|急診|住院|出院|手術|開刀|用藥|處方|服藥|醫囑"
        r"|身心障礙|重大傷病|罹患|確診|精神科|身心科|心理諮商|復健|化療|洗腎|懷孕|流產"
        r"|diagnos|medical record|prescription",
        re.IGNORECASE,
    ),
    "HEALTH_CHECK": re.compile(r"健康檢查|健檢|體檢|health check", re.IGNORECASE),
    "GENETIC": re.compile(r"基因|遺傳|genetic", re.IGNORECASE),
    "SEX_LIFE": re.compile(r"性生活|性傾向|性病|sexual orientation", re.IGNORECASE),
    "CRIMINAL_RECORD": re.compile(
        r"前科|犯罪紀錄|刑事紀錄|良民證|判刑|緩刑|假釋|通緝|criminal record",
        re.IGNORECASE,
    ),
}


class SensitiveContentError(ValueError):
    """Raised in strict mode. Carries category names only, never the text."""

    def __init__(self, categories: list[str]) -> None:
        self.categories = categories
        super().__init__("special-category personal data: " + ", ".join(categories))


def find_sensitive(text: str) -> list[str]:
    """Categories mentioned in text, in declaration order."""
    normalized = normalize(text)
    return [name for name, pattern in SENSITIVE_CATEGORIES.items() if pattern.search(normalized)]
