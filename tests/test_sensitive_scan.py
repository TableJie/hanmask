import importlib.util
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "sensitive_scan", Path(__file__).resolve().parent.parent / "scripts" / "sensitive_scan.py"
)
scan = importlib.util.module_from_spec(_SPEC)
sys.modules["sensitive_scan"] = scan
_SPEC.loader.exec_module(scan)


def pii(text):
    from hanmask.recognizers import find_entities

    return ((f"pii-{e.type}", e.text) for e in find_entities(text, enabled=scan.PII_TYPES))


def rules_of(hits):
    return [h.rule for h in hits]


def test_generic_rules():
    hits = scan.scan_text("docs/a.md", "見 \\\\fileserver\\share 或 192.168.1.20", scan.GENERIC_RULES, None)
    assert rules_of(hits) == ["unc-path", "private-ip"]


def test_documentation_ip_is_not_private():
    assert scan.scan_text("docs/a.md", "IP 203.0.113.45", scan.GENERIC_RULES, None) == []


def test_checksum_valid_pii_outside_tests_is_a_hit():
    hits = scan.scan_text("hanmask/proxy.py", "id = 'A123456789'", {}, pii)
    assert rules_of(hits) == ["pii-TW_ID"]
    # Masked in the report, never in full.
    assert "A123456789" not in str(hits[0])


def test_tests_and_bench_are_exempt_from_pii():
    assert scan.scan_text("tests/test_x.py", "A123456789", {}, pii) == []
    assert scan.scan_text("bench/synth.py", "A123456789", {}, pii) == []


def test_bad_checksum_is_not_pii():
    assert scan.scan_text("hanmask/x.py", "A123456788", {}, pii) == []


def test_guard_words(tmp_path):
    guard = tmp_path / "guard-words.txt"
    guard.write_text("# company names\n範例公司\n/acme\\s*corp/\n", encoding="utf-8")
    rules = scan.load_guard_words(guard)
    hits = scan.scan_text("local/issue.md", "範例公司 與 ACME  Corp", rules, None)
    assert rules_of(hits) == ["guard-word#2", "guard-word#3"]


def test_missing_guard_file_skips_quietly(tmp_path):
    assert scan.load_guard_words(tmp_path / "none.txt") == {}


def test_allow_list_globs():
    allow = [{"path": "docs/**", "rule": "pii-*"}, {"path": "README.md", "rule": "private-ip"}]
    assert scan.is_allowed(allow, "docs/x/y.md", "pii-TW_ID")
    assert not scan.is_allowed(allow, "docs/x/y.md", "private-ip")
    assert scan.is_allowed(allow, "README.md", "private-ip")
    assert not scan.is_allowed(allow, "README.zh-TW.md", "private-ip")


def test_cli_exit_codes(tmp_path, monkeypatch):
    monkeypatch.setenv("HANMASK_GUARD_WORDS", str(tmp_path / "none.txt"))
    clean, dirty = tmp_path / "clean.md", tmp_path / "dirty.md"
    clean.write_text("nothing here", encoding="utf-8")
    dirty.write_text("host 10.0.0.5", encoding="utf-8")
    assert scan.main([str(clean)]) == 0
    assert scan.main([str(dirty)]) == 1
    monkeypatch.setenv("HANMASK_SCAN_MODE", "warn")
    assert scan.main(["--hook", str(dirty)]) == 0


@pytest.mark.parametrize("flag", [[], ["--skip-pii"]])
def test_skip_pii_flag(tmp_path, monkeypatch, flag):
    monkeypatch.setenv("HANMASK_GUARD_WORDS", str(tmp_path / "none.txt"))
    draft = tmp_path / "issue.md"
    draft.write_text("身分證 A123456789", encoding="utf-8")
    assert scan.main([*flag, str(draft)]) == (0 if flag else 1)
