"""Block content that must not reach this public repo or a from-dog Issue.

    python scripts/sensitive_scan.py <file...>       scan files
    python scripts/sensitive_scan.py --staged        scan the git index (pre-commit)
    python scripts/sensitive_scan.py --all           scan every tracked file
    python scripts/sensitive_scan.py --message FILE  scan a commit message (commit-msg)

Rules:
  guard words   local/guard-words.txt, one string or /regex/ per line, # for
                comments. Gitignored; it names the company, so it only exists
                where real data does.
  generic       UNC paths and private IPv4 addresses.
  PII           checksum-valid TW_ID, TW_UBN and CREDIT_CARD found by hanmask
                itself. tests/ and bench/ hold synthetic values and are exempt.
                --skip-pii turns this off for Issue drafts, whose synthetic
                values are checksum-valid by design.

--hook exits 1 on a hit only when HANMASK_SCAN_MODE is "block" (the default);
"warn" reports and exits 0. Without --hook any hit exits 1.
Exemptions: scripts/sensitive_scan_allow.json, [{"path", "rule", "reason"}];
path may end in /**, rule is a glob ("pii-*", "*"). Hits print masked, never
in full.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parent.parent
GUARD_FILE = Path(os.environ.get("HANMASK_GUARD_WORDS", ROOT / "local" / "guard-words.txt"))
ALLOW_FILE = Path(os.environ.get("HANMASK_SCAN_ALLOW", ROOT / "scripts" / "sensitive_scan_allow.json"))
MAX_BYTES = 5 * 1024 * 1024
PII_EXEMPT = ("tests/**", "bench/**")
PII_TYPES = {"TW_ID", "TW_UBN", "CREDIT_CARD"}

GENERIC_RULES = {
    "unc-path": re.compile(r"\\\\[A-Za-z][\w.-]{2,}\\[\w$.-]+"),
    "private-ip": re.compile(
        r"(?<![\d.])(?:10(?:\.\d{1,3}){3}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}|192\.168(?:\.\d{1,3}){2})(?![\d.]*\d)"
    ),
}


@dataclass(frozen=True)
class Hit:
    target: str
    line: int
    rule: str
    snippet: str

    def __str__(self) -> str:
        return f"{self.target}:{self.line}  {self.rule}  {self.snippet}"


def mask(value: str) -> str:
    value = value[:40]
    if len(value) <= 3:
        return value[0] + "*" * (len(value) - 1)
    return value[:2] + "*" * (len(value) - 3) + value[-1]


def load_guard_words(path: Path = GUARD_FILE) -> dict[str, re.Pattern[str]]:
    if not path.exists():
        print(f"[sensitive-scan] no {path.name}: guard-word check skipped", file=sys.stderr)
        return {}
    rules: dict[str, re.Pattern[str]] = {}
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.fullmatch(r"/(.+)/[a-z]*", line)
        try:
            rules[f"guard-word#{i}"] = re.compile(m.group(1) if m else re.escape(line), re.IGNORECASE)
        except re.error:
            print(f"[sensitive-scan] guard word on line {i} is not a valid regex, skipped", file=sys.stderr)
    return rules


def load_allow(path: Path = ALLOW_FILE) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print("[sensitive-scan] allow list is not valid JSON, ignored", file=sys.stderr)
        return []
    return [a for a in data if isinstance(a, dict) and isinstance(a.get("path"), str)]


def _path_matches(pattern: str, target: str) -> bool:
    if pattern.endswith("/**"):
        return target.startswith(pattern[:-2])
    return fnmatch.fnmatchcase(target, pattern)


def is_allowed(allow: list[dict[str, str]], target: str, rule: str) -> bool:
    # rule is a glob too: "pii-*" covers every PII type.
    return any(
        _path_matches(a["path"], target) and fnmatch.fnmatchcase(rule, a.get("rule", "*"))
        for a in allow
    )


def _pii_finder() -> Callable[[str], Iterable[tuple[str, str]]] | None:
    try:
        sys.path.insert(0, str(ROOT))
        from hanmask.recognizers import find_entities
    except ImportError:
        print("[sensitive-scan] hanmask not importable: PII check skipped", file=sys.stderr)
        return None
    return lambda text: ((f"pii-{e.type}", e.text) for e in find_entities(text, enabled=PII_TYPES))


def scan_text(
    target: str,
    text: str,
    rules: dict[str, re.Pattern[str]],
    pii: Callable[[str], Iterable[tuple[str, str]]] | None,
) -> list[Hit]:
    hits: list[Hit] = []
    check_pii = pii is not None and not any(_path_matches(p, target) for p in PII_EXEMPT)
    for n, line in enumerate(text.splitlines(), 1):
        for name, pattern in rules.items():
            hits.extend(Hit(target, n, name, mask(m.group(0))) for m in pattern.finditer(line) if m.group(0))
        if check_pii:
            hits.extend(Hit(target, n, rule, mask(value)) for rule, value in pii(line))
    return hits


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


def _targets(args: argparse.Namespace) -> Iterable[tuple[str, Callable[[], bytes | None]]]:
    if args.staged:
        names = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").decode().split("\0")
        for name in filter(None, names):
            yield name, lambda name=name: _git("show", f":{name}")
    elif args.all:
        for name in filter(None, _git("ls-files", "-z").decode().split("\0")):
            path = ROOT / name
            yield name, lambda path=path: path.read_bytes() if path.is_file() else None
    elif args.message:
        path = Path(args.message)
        yield "COMMIT_MESSAGE", lambda: b"\n".join(
            l for l in path.read_bytes().splitlines() if not l.startswith(b"#")
        )
    else:
        for name in args.files:
            path = Path(name)
            yield name.replace("\\", "/"), lambda path=path: path.read_bytes() if path.is_file() else None


def run(args: argparse.Namespace) -> list[Hit]:
    rules = {**GENERIC_RULES, **load_guard_words()}
    pii = None if args.skip_pii else _pii_finder()
    allow = load_allow()
    hits: list[Hit] = []
    for target, read in _targets(args):
        if target != "COMMIT_MESSAGE":
            hits.extend(scan_text(target, target, rules, None))  # file names too
        data = read()
        if not data or len(data) > MAX_BYTES or b"\0" in data[:8000]:
            continue
        hits.extend(scan_text(target, data.decode("utf-8", errors="replace"), rules, pii))
    return [h for h in hits if not is_allowed(allow, h.target, h.rule)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan for content that must not be published.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--all", action="store_true")
    mode.add_argument("--message", metavar="FILE")
    parser.add_argument("--hook", action="store_true")
    parser.add_argument("--skip-pii", action="store_true")
    parser.add_argument("files", nargs="*")
    args = parser.parse_args(argv)

    hits = run(args)
    if not hits:
        return 0
    print("\n".join(map(str, hits)))
    print(f"[sensitive-scan] {len(hits)} hit(s)", file=sys.stderr)
    if args.hook and os.environ.get("HANMASK_SCAN_MODE", "block").lower() == "warn":
        print("[sensitive-scan] warn mode: commit not blocked", file=sys.stderr)
        return 0
    if args.hook:
        print(
            "[sensitive-scan] blocked. Synthetic data that trips a rule goes in "
            "scripts/sensitive_scan_allow.json with a reason.",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
