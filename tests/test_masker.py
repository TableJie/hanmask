import pytest

from hanmask import Masker, SensitiveContentError, StreamRestorer, Vault, find_sensitive, restore


def test_strict_mode_blocks_special_categories():
    with pytest.raises(SensitiveContentError) as exc:
        Masker(strict=True).mask("請假原因：憂鬱症回診，身分證 A123456789")
    assert exc.value.categories == ["MEDICAL"]
    # The error never carries the text itself.
    assert "A123456789" not in str(exc.value)


def test_non_strict_mode_masks_and_forwards():
    masked, _ = Masker().mask("請假原因：憂鬱症回診，身分證 A123456789")
    assert masked == "請假原因：憂鬱症回診，身分證 <TW_ID_1>"


def test_find_sensitive_categories():
    assert find_sensitive("體檢報告與前科紀錄") == ["HEALTH_CHECK", "CRIMINAL_RECORD"]
    assert find_sensitive("訂單編號 12345678") == []


def test_round_trip():
    original = "請聯絡王先生 0912-345-678 或 wang@example.com，身分證 A123456789。"
    masked, vault = Masker().mask(original)
    assert "0912-345-678" not in masked
    assert "wang@example.com" not in masked
    assert "A123456789" not in masked
    assert "<PHONE_1>" in masked and "<EMAIL_1>" in masked and "<TW_ID_1>" in masked
    assert restore(masked, vault) == original


def test_same_value_same_placeholder_across_messages():
    m = Masker()
    vault = Vault()
    a, _ = m.mask("電話 0912345678", vault)
    b, _ = m.mask("再確認 0912345678 與 0987654321", vault)
    assert a == "電話 <PHONE_1>"
    assert b == "再確認 <PHONE_1> 與 <PHONE_2>"
    assert vault.counts() == {"PHONE": 2}


def test_unknown_placeholder_is_left_alone():
    _, vault = Masker().mask("0912345678")
    assert restore("<PHONE_1> and <PHONE_9>", vault) == "0912345678 and <PHONE_9>"


def test_stream_restore_split_placeholder():
    _, vault = Masker().mask("0912345678 a@b.co")
    r = StreamRestorer(vault)
    chunks = ["好的，我會打 <PHO", "NE_1", "> 並寄信到 <", "EMAIL_1>", "。a < b"]
    out = "".join(r.feed(c) for c in chunks) + r.flush()
    assert out == "好的，我會打 0912345678 並寄信到 a@b.co。a < b"


def test_stream_does_not_hold_plain_text():
    _, vault = Masker().mask("0912345678")
    r = StreamRestorer(vault)
    assert r.feed("hello ") == "hello "
    assert r.feed("x <") == "x "
    assert r.feed("3") == "<3"
    assert r.flush() == ""


def test_full_width_round_trip_keeps_original_form():
    original = "請回電０９１２３４５６７８，統一編號０４５９５２５７。"
    masked, vault = Masker().mask(original)
    assert masked == "請回電<PHONE_1>，統一編號<TW_UBN_1>。"
    assert restore(masked, vault) == original
