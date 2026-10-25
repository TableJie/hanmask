"""Precision and recall of the recognizers on synthetic data.

    python -m bench.run --n 1000 --seed 0

A prediction is correct only with the exact gold type and span. "leaked"
counts gold values that no prediction overlaps at all: the values that would
reach the LLM unmasked.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field

from hanmask.recognizers import find_entities

from .synth import GENERATORS, Sample, Span, generate


def _overlaps(a: Span, b: Span) -> bool:
    return a.start < b.end and b.start < a.end


@dataclass
class Report:
    samples: int = 0
    tp: Counter[str] = field(default_factory=Counter)
    fp: Counter[str] = field(default_factory=Counter)
    fn: Counter[str] = field(default_factory=Counter)
    leaked: Counter[str] = field(default_factory=Counter)
    fp_by_decoy: Counter[str] = field(default_factory=Counter)


def evaluate(samples: list[Sample]) -> Report:
    r = Report(samples=len(samples))
    for s in samples:
        pred = {Span(e.type, e.start, e.end) for e in find_entities(s.text)}
        gold = set(s.gold)
        for p in pred - gold:
            r.fp[p.label] += 1
            for d in s.decoys:
                if _overlaps(p, d):
                    r.fp_by_decoy[f"{d.label} -> {p.label}"] += 1
        for g in gold:
            if g in pred:
                r.tp[g.label] += 1
                continue
            r.fn[g.label] += 1
            if not any(_overlaps(g, p) for p in pred):
                r.leaked[g.label] += 1
    return r


def _pct(num: int, den: int) -> str:
    return f"{num / den:.1%}" if den else "-"


def _row(label: str, tp: int, fp: int, fn: int, leaked: int) -> str:
    return (
        f"{label:<14}{tp + fn:>6}{tp:>6}{fp:>6}{fn:>6}{leaked:>8}"
        f"{_pct(tp, tp + fp):>11}{_pct(tp, tp + fn):>9}"
    )


def format_report(r: Report) -> str:
    lines = [
        f"{r.samples} samples",
        "",
        f"{'type':<14}{'gold':>6}{'tp':>6}{'fp':>6}{'fn':>6}{'leaked':>8}{'precision':>11}{'recall':>9}",
    ]
    for label in GENERATORS:
        lines.append(_row(label, r.tp[label], r.fp[label], r.fn[label], r.leaked[label]))
    lines.append(_row("ALL", *(sum(c.values()) for c in (r.tp, r.fp, r.fn, r.leaked))))
    if r.fp_by_decoy:
        lines += ["", "false positives on decoys:"]
        lines += [f"  {k:<28}{v:>5}" for k, v in r.fp_by_decoy.most_common()]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark hanmask recognizers on synthetic data.")
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--full-width-rate", type=float, default=0.15)
    args = parser.parse_args()
    print(format_report(evaluate(generate(args.n, args.seed, args.full_width_rate))))


if __name__ == "__main__":
    main()
