"""Restore placeholders in a streamed response.

A placeholder such as <PHONE_1> can be split across chunks ("<PHO" + "NE_1>").
StreamRestorer holds back only the tail that could still become a placeholder
and emits everything else immediately.
"""

from __future__ import annotations

import re

from .masker import Vault, restore

_PARTIAL_RE = re.compile(r"<(?:[A-Z][A-Z_0-9]*)?$")


class StreamRestorer:
    def __init__(self, vault: Vault) -> None:
        self.vault = vault
        self._pending = ""

    def feed(self, chunk: str) -> str:
        text = self._pending + chunk
        self._pending = ""
        m = _PARTIAL_RE.search(text)
        if m and len(m.group(0)) < max(self.vault.max_placeholder_len, 1):
            self._pending = m.group(0)
            text = text[: m.start()]
        return restore(text, self.vault)

    def flush(self) -> str:
        """Call at end of stream to emit whatever is still held back."""
        text, self._pending = self._pending, ""
        return restore(text, self.vault)
