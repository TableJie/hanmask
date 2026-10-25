import pytest

from hanmask.recognizers import (
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


@pytest.mark.parametrize(
    "text, expected",
    [
        ("護照號碼：312345678", ("PASSPORT", "312345678")),
        ("Passport No. E12345678", ("PASSPORT", "E12345678")),
        ("健保卡號 0000 1234 5678", ("TW_NHI", "0000 1234 5678")),
        ("匯款至 (013) 帳號 1234-5678-9012", ("BANK_ACCOUNT", "1234-5678-9012")),
        ("戶頭0912345678", ("BANK_ACCOUNT", "0912345678")),
        ("護照號碼：３１２３４５６７８", ("PASSPORT", "３１２３４５６７８")),
    ],
)
def test_keyword_types_with_context(text, expected):
    assert types(text) == [expected]


@pytest.mark.parametrize("text", ["訂單312345678", "料號 0000 1234 5678", "交易序號 123456789012"])
def test_keyword_types_need_context(text):
    assert types(text) == []


def test_context_does_not_cross_clause():
    # 帳號 belongs to the first clause, so the number stays a phone.
    assert types("帳號是 jay，電話 0912345678") == [("PHONE", "0912345678")]


def test_context_window_is_limited():
    assert types("護照" + "的" * 30 + "312345678") == []


def test_tw_id_wins_over_passport():
    assert types("護照號碼 A123456789") == [("TW_ID", "A123456789")]
