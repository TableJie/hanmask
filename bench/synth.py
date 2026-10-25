"""Synthetic Traditional Chinese text with gold PII spans.

Values are generated with their own checksum code, independent of
hanmask.recognizers, so a validator bug shows up as missed entities instead
of being copied into the gold labels. Decoys (unlabelled numbers, IDs with a
wrong check digit) carry no gold label: any match on them is a false
positive.
"""

from __future__ import annotations

import random
import re
import string
from dataclasses import dataclass, field

_LETTER_CODES = {
    "A": 10, "B": 11, "C": 12, "D": 13, "E": 14, "F": 15, "G": 16, "H": 17,
    "I": 34, "J": 18, "K": 19, "L": 20, "M": 21, "N": 22, "O": 35, "P": 23,
    "Q": 24, "R": 25, "S": 26, "T": 27, "U": 28, "V": 29, "W": 32, "X": 30,
    "Y": 31, "Z": 33,
}


@dataclass(frozen=True)
class Span:
    label: str
    start: int
    end: int


@dataclass
class Sample:
    text: str
    gold: list[Span] = field(default_factory=list)
    # Decoy spans, labelled by slot name, for attributing false positives.
    decoys: list[Span] = field(default_factory=list)


def _digits(rng: random.Random, n: int) -> str:
    return "".join(rng.choice(string.digits) for _ in range(n))


def _tw_id_check(body: str) -> int:
    code = _LETTER_CODES[body[0]]
    second = _LETTER_CODES[body[1]] % 10 if body[1].isalpha() else int(body[1])
    nums = [code // 10, code % 10, second] + [int(c) for c in body[2:]]
    total = sum(d * w for d, w in zip(nums, (1, 9, 8, 7, 6, 5, 4, 3, 2, 1)))
    return (10 - total % 10) % 10


def tw_id(rng: random.Random) -> str:
    # Mostly national IDs; resident certificates in both new (8/9) and old (A-D) style.
    second = rng.choice("12" * 4 + "89AB")
    body = rng.choice(string.ascii_uppercase) + second + _digits(rng, 7)
    return body + str(_tw_id_check(body))


def bad_tw_id(rng: random.Random) -> str:
    good = tw_id(rng)
    return good[:-1] + str((int(good[-1]) + rng.randint(1, 9)) % 10)


def _ubn_ok(value: str) -> bool:
    total = sum(sum(divmod(int(c) * w, 10)) for c, w in zip(value, (1, 2, 1, 2, 1, 2, 4, 1)))
    return total % 5 == 0 or (value[6] == "7" and (total + 1) % 5 == 0)


def tw_ubn(rng: random.Random) -> str:
    while True:
        value = _digits(rng, 8)
        if _ubn_ok(value):
            return value


def credit_card(rng: random.Random) -> str:
    body = rng.choice("45") + _digits(rng, 14)
    total = 0
    for i, c in enumerate(reversed(body)):
        d = int(c)
        if i % 2 == 0:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    number = body + str((10 - total % 10) % 10)
    sep = rng.choice(["", " ", "-"])
    return sep.join(number[i:i + 4] for i in range(0, 16, 4))


def phone(rng: random.Random) -> str:
    if rng.random() < 0.7:
        a, b, c = "9" + _digits(rng, 2), _digits(rng, 3), _digits(rng, 3)
        return rng.choice([
            f"0{a}-{b}-{c}", f"0{a}{b}{c}", f"0{a} {b} {c}",
            f"+886 {a} {b} {c}", f"+886-{a}-{b}-{c}",
        ])
    area = rng.choice("2345678")
    head = _digits(rng, 4 if area == "2" else 3)
    tail = _digits(rng, 4)
    return rng.choice([f"0{area}-{head}-{tail}", f"(0{area}){head}-{tail}", f"0{area}{head}{tail}"])


def email(rng: random.Random) -> str:
    user = rng.choice(["wang", "chen.yt", "lin_88", "amy.huang", "service", "kuo2024"])
    domain = rng.choice(["example.com", "example.com.tw", "mail.example.org", "corp.example.net"])
    return f"{user}@{domain}"


def passport(rng: random.Random) -> str:
    return rng.choice("13") + _digits(rng, 8)


def tw_nhi(rng: random.Random) -> str:
    sep = rng.choice(["", " ", "-"])
    return sep.join(["0000", _digits(rng, 4), _digits(rng, 4)])


def bank_account(rng: random.Random) -> str:
    value = _digits(rng, rng.randint(10, 14))
    return value if rng.random() < 0.6 else f"{value[:3]}-{value[3:6]}-{value[6:]}"


def _letters(rng: random.Random, n: int) -> str:
    return "".join(rng.choice(string.ascii_uppercase) for _ in range(n))


def invoice(rng: random.Random) -> str:
    return _letters(rng, 2) + _digits(rng, 8)


def order_no(rng: random.Random) -> str:
    if rng.random() < 0.3:
        return f"PO-{rng.randint(2020, 2026)}-{_digits(rng, 5)}"
    return _digits(rng, rng.randint(8, 10))


def part_no(rng: random.Random) -> str:
    return f"{_letters(rng, 2)}-{_digits(rng, 4)}{_letters(rng, 1)}"


_CITIES = ("台北市", "臺北市", "新北市", "桃園市", "台中市", "高雄市", "宜蘭縣", "花蓮縣")
_DISTRICTS = ("大安區", "板橋區", "中壢區", "西屯區", "苓雅區", "羅東鎮", "吉安鄉")
_ROADS = ("忠孝東路", "中正路", "文化路", "民生路", "台灣大道", "中山北路", "復興街")


def address(rng: random.Random) -> str:
    parts = [rng.choice(_CITIES), rng.choice(_DISTRICTS), rng.choice(_ROADS)]
    if rng.random() < 0.5:
        parts.append(rng.choice("一二三四五") + "段")
    if rng.random() < 0.3:
        parts.append(f"{rng.randint(1, 300)}巷")
    sp = rng.choice(["", " "])
    tail = f"{sp}{rng.randint(1, 999)}{sp}號"
    if rng.random() < 0.6:
        tail += f"{sp}{rng.randint(2, 30)}{sp}樓"
    return "".join(parts) + tail


def birth_date(rng: random.Random) -> str:
    y, m, d = rng.randint(1960, 2005), rng.randint(1, 12), rng.randint(1, 28)
    return rng.choice([f"{y}/{m:02d}/{d:02d}", f"{y}-{m:02d}-{d:02d}", f"民國{y - 1911}年{m}月{d}日"])


def salary(rng: random.Random) -> str:
    monthly = rng.randint(28, 150) * 1000
    return rng.choice([f"{monthly:,}", f"NT$ {monthly:,}", f"{monthly / 10000:g}萬"])


def ip_address(rng: random.Random) -> str:
    return ".".join(str(rng.randint(1, 254)) for _ in range(4))


def uuid(rng: random.Random) -> str:
    h = "".join(rng.choice("0123456789abcdef") for _ in range(32))
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


def social_id(rng: random.Random) -> str:
    return rng.choice(["amy", "chen.yt", "lin_", "kuo", "wang-"]) + _digits(rng, 4)


def org_name(rng: random.Random) -> str:
    name = rng.choice(["大華科技", "永興實業", "群光電子", "明日設計", "海岸物流", "晨光餐飲"])
    return name + rng.choice(["股份有限公司", "有限公司", "企業社", "工作室"])


GENERATORS = {
    "TW_ID": tw_id,
    "TW_UBN": tw_ubn,
    "CREDIT_CARD": credit_card,
    "PHONE": phone,
    "EMAIL": email,
    "PASSPORT": passport,
    "TW_NHI": tw_nhi,
    "BANK_ACCOUNT": bank_account,
    "ORDER_NO": order_no,
    "INVOICE_NO": invoice,
    "PART_NO": part_no,
    "REF_NO": lambda rng: _digits(rng, rng.randint(9, 12)),
    "ADDRESS": address,
    "BIRTH_DATE": birth_date,
    "SALARY": salary,
    "IP_ADDRESS": ip_address,
    "UUID": uuid,
    "SOCIAL_ID": social_id,
    "ORG_NAME": org_name,
}

# Unlabelled numbers that must stay unmasked. DIGITS8 passes the UBN
# checksum one time in five: the residual false-positive rate.
DECOYS = {
    "BAD_TW_ID": bad_tw_id,
    "DIGITS8": lambda rng: _digits(rng, 8),
    "AMOUNT": lambda rng: f"{rng.randint(1, 999)},{_digits(rng, 3)}",
}

TEMPLATES = (
    "請聯絡王先生 {PHONE}，身分證字號 {TW_ID}。",
    "客戶身分證{TW_ID}，手機{PHONE}",
    "公司統編{TW_UBN}，聯絡窗口 {EMAIL}",
    "發票抬頭請開統一編號 {TW_UBN}，發票號碼 {INVOICE_NO}",
    "信用卡號 {CREDIT_CARD}，本期應繳 {AMOUNT} 元",
    "訂單編號 {ORDER_NO} 已出貨，收件人電話 {PHONE}",
    "物流單號 {ORDER_NO}，預計明天送達",
    "交易序號 {REF_NO} 已完成，退款至信用卡 {CREDIT_CARD}",
    "護照號碼：{PASSPORT}，效期至 2031 年",
    "旅客 Passport No. {PASSPORT}，聯絡信箱 {EMAIL}",
    "健保卡號 {TW_NHI}，就診日期 10/25",
    "請提供健保卡卡號：{TW_NHI}",
    "匯款帳號：{BANK_ACCOUNT}，戶名陳小姐",
    "轉帳至 (812) {BANK_ACCOUNT}，金額 {AMOUNT} 元",
    "薪轉戶頭 {BANK_ACCOUNT}，身分證 {TW_ID}",
    "居留證號碼 {TW_ID}，電話 {PHONE}",
    "料號 {PART_NO} 共 {AMOUNT} 件",
    "備註 {BAD_TW_ID} 對應的客戶電話是 {PHONE}",
    "會員編號 {REF_NO}，Email：{EMAIL}",
    "傳真 {PHONE}，統編 {TW_UBN}",
    "請於 10/31 前回覆，案件編號 {REF_NO}",
    "Order No. {ORDER_NO}，invoice {INVOICE_NO}",
    "本月營收 {DIGITS8} 元，較上月成長",
    "帳號是 jay，手機 {PHONE}",
    "持卡人身分證 {TW_ID}，卡號 {CREDIT_CARD}",
    "申請人：林小姐，身分證 {TW_ID}，戶籍電話 {PHONE}，信箱 {EMAIL}",
    "報價單號 {ORDER_NO}，廠商統編 {TW_UBN}",
    # HR
    "新進員工身分證 {TW_ID}，生日 {BIRTH_DATE}，手機 {PHONE}",
    "戶籍地址：{ADDRESS}，緊急聯絡人電話 {PHONE}",
    "員工編號 {REF_NO}，薪轉帳號 {BANK_ACCOUNT}，月薪 {SALARY} 元",
    "出生日期：{BIRTH_DATE}，私人信箱 {EMAIL}，LINE ID：{SOCIAL_ID}",
    "明年起薪調整為 {SALARY}，年終另計",
    # AR
    "客戶：{ORG_NAME}，統編 {TW_UBN}，聯絡電話 {PHONE}",
    "應收單號 {ORDER_NO}，發票號碼 {INVOICE_NO}，應收金額 NT$ {AMOUNT}",
    "請匯款給{ORG_NAME}，帳號 {BANK_ACCOUNT}",
    "合約編號 {REF_NO}，逾期未付，催收信箱 {EMAIL}",
    # Marketing
    "會員生日 {BIRTH_DATE}，寄送地址：{ADDRESS}",
    "登入 IP {IP_ADDRESS}，裝置 ID {UUID}",
    "得獎會員 IG: {SOCIAL_ID}，手機 {PHONE}",
    "合作廠商 {ORG_NAME} 的報價單號 {ORDER_NO}",
)

_SLOT = re.compile(r"\{([A-Z0-9_]+)\}")
# Email stays half-width; IDs and numbers are sometimes typed full-width.
_FULL_WIDTH_SKIP = {"EMAIL"}


def to_full_width(value: str) -> str:
    return "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in value)


def make_sample(rng: random.Random, template: str, full_width_rate: float = 0.15) -> Sample:
    sample = Sample("")
    parts: list[str] = []
    pos = 0
    for i, piece in enumerate(_SLOT.split(template)):
        if i % 2 == 0:
            value = piece
        else:
            value = (GENERATORS.get(piece) or DECOYS[piece])(rng)
            if piece not in _FULL_WIDTH_SKIP and rng.random() < full_width_rate:
                value = to_full_width(value)
            span = Span(piece, pos, pos + len(value))
            (sample.gold if piece in GENERATORS else sample.decoys).append(span)
        parts.append(value)
        pos += len(value)
    sample.text = "".join(parts)
    return sample


def generate(n: int, seed: int = 0, full_width_rate: float = 0.15) -> list[Sample]:
    rng = random.Random(seed)
    return [make_sample(rng, rng.choice(TEMPLATES), full_width_rate) for _ in range(n)]
