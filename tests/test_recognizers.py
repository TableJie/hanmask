import pytest

from hanmask.recognizers import (
    PII_TYPES,
    find_entities,
    is_valid_luhn,
    is_valid_tw_id,
    is_valid_tw_ubn,
)


def types(text, enabled=None):
    return [(e.type, e.text) for e in find_entities(text, enabled=enabled)]


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
    assert types("備註A123456788") == []


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
    assert types("備註Ａ１２３４５６７８８") == []


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
    assert types(text, enabled=PII_TYPES) == []


def test_context_does_not_cross_clause():
    # 帳號 belongs to the first clause, so the number stays a phone.
    assert types("帳號是 jay，電話 0912345678") == [("PHONE", "0912345678")]


def test_context_window_is_limited():
    assert types("護照" + "的" * 30 + "312345678") == []


def test_tw_id_wins_over_passport():
    assert types("護照號碼 A123456789") == [("TW_ID", "A123456789")]


@pytest.mark.parametrize(
    "text, expected",
    [
        # The positive keyword is checked first: 統一編號 contains 編號.
        ("統一編號 04595257", [("TW_UBN", "04595257")]),
        ("訂單編號 04595257", []),
        ("物流單號 0423456789", []),
        ("發票號碼 AB12345677", []),
        ("訂單聯絡電話 0912345678", [("PHONE", "0912345678")]),
        # No keyword either way: the pattern and checksum decide.
        ("04595257", [("TW_UBN", "04595257")]),
        ("請回電 0912345678", [("PHONE", "0912345678")]),
    ],
)
def test_keywords_resolve_in_order(text, expected):
    # PII only: with business types on, the labelled values become ORDER_NO etc.
    assert types(text, enabled=PII_TYPES) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("訂單編號 04595257", [("ORDER_NO", "04595257")]),
        ("Order No. PO-2024-00123", [("ORDER_NO", "PO-2024-00123")]),
        ("物流單號：0423456789", [("ORDER_NO", "0423456789")]),
        ("發票號碼 AB12345677", [("INVOICE_NO", "AB12345677")]),
        ("料號 XC-7731B", [("PART_NO", "XC-7731B")]),
        ("交易序號 123456789012", [("REF_NO", "123456789012")]),
        ("統一編號 04595257", [("TW_UBN", "04595257")]),
        ("身分證編號 A123456789", [("TW_ID", "A123456789")]),
        # The label must sit right before the value.
        ("訂單聯絡電話 0912345678", [("PHONE", "0912345678")]),
        # Too short or no digit: a year or a word is not an identifier.
        ("訂單 2024 年的報表", []),
        ("料號 ABCDEF", []),
    ],
)
def test_business_identifiers(text, expected):
    assert types(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("戶籍地址：台北市大安區忠孝東路四段 100 號 5 樓", [("ADDRESS", "台北市大安區忠孝東路四段 100 號 5 樓")]),
        ("寄到 106臺北市大安區信義路三段12巷3弄4之1號", [("ADDRESS", "106臺北市大安區信義路三段12巷3弄4之1號")]),
        ("宜蘭縣羅東鎮中正路 8 號", [("ADDRESS", "宜蘭縣羅東鎮中正路 8 號")]),
        ("總部設在台北市大安區", []),
        ("生日 1990/05/12", [("BIRTH_DATE", "1990/05/12")]),
        ("出生日期：民國79年5月12日", [("BIRTH_DATE", "民國79年5月12日")]),
        ("生日禮券 3 張", []),
        ("月薪 52,000 元", [("SALARY", "52,000")]),
        ("年薪約 NT$ 1,200,000", [("SALARY", "NT$ 1,200,000")]),
        ("獎金 5.2萬", [("SALARY", "5.2萬")]),
        ("年終 2 個月", []),
        ("應收金額 NT$ 1,250,000", []),
        ("登入 IP 203.0.113.45", [("IP_ADDRESS", "203.0.113.45")]),
        ("版本 1.2.3.4 已上線", []),
        ("裝置 3f2a9c1e-77b0-4c1d-9a2e-5b6c7d8e9f00", [("UUID", "3f2a9c1e-77b0-4c1d-9a2e-5b6c7d8e9f00")]),
        ("LINE ID：amy_0512", [("SOCIAL_ID", "amy_0512")]),
        ("IG: chen.yt.88。", [("SOCIAL_ID", "chen.yt.88")]),
        ("用 LINE Pay 付款", []),
        ("勞保證號 12345678", [("REF_NO", "12345678")]),
    ],
)
def test_hr_ar_marketing_types(text, expected):
    assert types(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("客戶：大華科技股份有限公司", [("ORG_NAME", "大華科技股份有限公司")]),
        # The particle before the name stays outside the span.
        ("請匯款給大華科技有限公司", [("ORG_NAME", "大華科技有限公司")]),
        ("Acme Trading Co., Ltd. 的報價", [("ORG_NAME", "Acme Trading Co., Ltd.")]),
        ("本公司與貴公司", []),
    ],
)
def test_org_names(text, expected):
    assert types(text) == expected
