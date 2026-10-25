# hanmask

English | [繁體中文](README.zh-TW.md)

Self-hosted LLM proxy that masks PII before it leaves your network, and restores it in the response. CJK-ready.

## Status

Early development. The rule-based recognizers and the reversible mask/restore core are in place; the HTTP proxy is next. Traditional Chinese text is handled natively: full-width digits and letters (０９１２－３４５－６７８), Taiwan IDs and resident certificates, passport, NHI card and bank account numbers (masked only next to a keyword such as 護照 or 帳號), and values written flush against Chinese characters. See [PLAN.md](PLAN.md).

```python
from hanmask import Masker, restore

masked, vault = Masker().mask("請聯絡 0912-345-678，身分證 A123456789")
# masked == "請聯絡 <PHONE_1>，身分證 <TW_ID_1>"
restore(masked, vault)  # back to the original
```

## Development

```bash
pip install -e '.[dev]'
pytest
```
