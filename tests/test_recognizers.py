import pytest

from maskgate.recognizers import (
    find_entities,
    is_valid_luhn,
    is_valid_tw_id,
    is_valid_tw_ubn,
)


def types(text):
    return [(e.type, e.text) for e in find_entities(text)]


@pytest.mark.parametrize("value", ["A123456789", "a123456789", "F131104093", "A800000014", "AB12345677", "FD12345676"])
def test_tw_id_valid(value):
    assert is_valid_tw_id(value)


@pytest.mark.parametrize("value", ["A123456788", "A323456789", "1234567890", "A12345678", "AB12345678", "AE12345677"])
def test_tw_id_invalid(value):
    assert not is_valid_tw_id(value)


@pytest.mark.parametrize("value", ["04595257", "22099131", "10458575"])
def test_ubn_valid(value):
    assert is_valid_tw_ubn(value)


@pytest.mark.parametrize("value", ["04595258", "12345678", "1234567"])
def test_ubn_invalid(value):
    assert not is_valid_tw_ubn(value)


def test_luhn():
    assert is_valid_luhn("4111 1111 1111 1111")
    assert not is_valid_luhn("4111 1111 1111 1112")


def test_finds_ids_inside_chinese_text():
    # No spaces around the values: CJK text must not block the match.
    assert types("客戶身分證A123456789，統編04595257。") == [
        ("TW_ID", "A123456789"),
        ("TW_UBN", "04595257"),
    ]


def test_bad_checksum_is_not_masked():
    assert types("訂單編號A123456788") == []


def test_phone_formats():
    text = "手機0912-345-678、0912345678、+886 912 345 678，市話(02)2345-6789、07-123-4567"
    assert [t for t, _ in types(text)] == ["PHONE"] * 5


def test_email_and_card():
    assert types("寄到 wang.xm@example.com.tw，卡號 4111-1111-1111-1111") == [
        ("EMAIL", "wang.xm@example.com.tw"),
        ("CREDIT_CARD", "4111-1111-1111-1111"),
    ]


def test_embedded_in_longer_alnum_is_ignored():
    assert types("SKU-XA123456789Z") == []


def test_enabled_filter():
    entities = find_entities("A123456789 a@b.co", enabled={"EMAIL"})
    assert [e.type for e in entities] == ["EMAIL"]


def test_full_width_values_in_traditional_chinese_text():
    # Original characters are reported; validation runs on the half-width form.
    text = "身分證字號：Ａ１２３４５６７８９，手機０９１２－３４５－６７８，市話（０２）２３４５－６７８９"
    assert types(text) == [
        ("TW_ID", "Ａ１２３４５６７８９"),
        ("PHONE", "０９１２－３４５－６７８"),
        ("PHONE", "（０２）２３４５－６７８９"),
    ]


def test_full_width_bad_checksum_is_not_masked():
    assert types("編號Ａ１２３４５６７８８") == []


def test_old_style_resident_certificate_in_text():
    assert types("居留證號碼AB12345677") == [("TW_ID", "AB12345677")]
