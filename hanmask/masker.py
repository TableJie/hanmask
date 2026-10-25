"""Reversible masking: swap PII for placeholders, then swap it back.

A Vault holds the placeholder <-> original mapping for one request. It lives
only in memory and is meant to be discarded when the request ends, so the
proxy never becomes a new place where PII is stored.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .recognizers import DEFAULT_RECOGNIZERS, Recognizer, find_entities
from .sensitive import SensitiveContentError, find_sensitive

PLACEHOLDER_RE = re.compile(r"<([A-Z][A-Z_]*_\d+)>")


@dataclass
class Vault:
    """Per-request mapping. The same original value always gets the same placeholder."""

    _by_placeholder: dict[str, str] = field(default_factory=dict)
    _by_original: dict[tuple[str, str], str] = field(default_factory=dict)
    _counters: Counter[str] = field(default_factory=Counter)

    def placeholder_for(self, entity_type: str, original: str) -> str:
        key = (entity_type, original)
        if key not in self._by_original:
            self._counters[entity_type] += 1
            placeholder = f"<{entity_type}_{self._counters[entity_type]}>"
            self._by_original[key] = placeholder
            self._by_placeholder[placeholder] = original
        return self._by_original[key]

    def original_for(self, placeholder: str) -> str | None:
        return self._by_placeholder.get(placeholder)

    def counts(self) -> dict[str, int]:
        """Distinct values masked per type — what the audit log records, never the values."""
        return dict(self._counters)

    @property
    def max_placeholder_len(self) -> int:
        return max((len(p) for p in self._by_placeholder), default=0)

    def __len__(self) -> int:
        return len(self._by_placeholder)


class Masker:
    def __init__(
        self,
        recognizers: tuple[Recognizer, ...] = DEFAULT_RECOGNIZERS,
        enabled: set[str] | None = None,
        strict: bool = False,
    ) -> None:
        self.recognizers = recognizers
        self.enabled = enabled
        self.strict = strict

    def mask(self, text: str, vault: Vault | None = None) -> tuple[str, Vault]:
        """Mask text. Pass the same vault for every message in one request.

        In strict mode, raises SensitiveContentError when the text mentions
        special-category data that rules cannot mask.
        """
        if self.strict and (categories := find_sensitive(text)):
            raise SensitiveContentError(categories)
        vault = vault if vault is not None else Vault()
        out: list[str] = []
        pos = 0
        for e in find_entities(text, self.recognizers, self.enabled):
            out.append(text[pos:e.start])
            out.append(vault.placeholder_for(e.type, e.text))
            pos = e.end
        out.append(text[pos:])
        return "".join(out), vault


def restore(text: str, vault: Vault) -> str:
    """Replace known placeholders with their originals; leave unknown ones untouched."""

    def sub(m: re.Match[str]) -> str:
        original = vault.original_for(m.group(0))
        return original if original is not None else m.group(0)

    return PLACEHOLDER_RE.sub(sub, text)
