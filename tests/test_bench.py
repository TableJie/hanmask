import random

from bench.run import evaluate, format_report
from bench.synth import GENERATORS, generate, to_full_width
from hanmask.recognizers import is_valid_luhn, is_valid_tw_id, is_valid_tw_ubn


def test_gold_spans_point_at_generated_values():
    for s in generate(200, seed=1):
        for g in s.gold + s.decoys:
            assert 0 <= g.start < g.end <= len(s.text)


def test_generated_values_pass_checksums():
    rng = random.Random(0)
    for _ in range(200):
        assert is_valid_tw_id(GENERATORS["TW_ID"](rng))
        assert is_valid_tw_ubn(GENERATORS["TW_UBN"](rng))
        assert is_valid_luhn(GENERATORS["CREDIT_CARD"](rng))


def test_full_width_is_length_preserving():
    assert to_full_width("A12-3") == "Ａ１２－３"


def test_report_has_no_leaks_on_seed_0():
    report = evaluate(generate(500, seed=0))
    assert sum(report.leaked.values()) == 0
    assert "ALL" in format_report(report)
