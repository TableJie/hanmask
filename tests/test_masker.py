from maskgate import Masker, StreamRestorer, Vault, restore


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
