# maskgate
Self-hosted LLM proxy that masks PII before it leaves your network, and restores it in the response. CJK-ready.

## Status

Early development. The rule-based recognizers and the reversible mask/restore core are in place; the HTTP proxy is next. See [PLAN.md](PLAN.md).

```python
from maskgate import Masker, restore

masked, vault = Masker().mask("請聯絡 0912-345-678，身分證 A123456789")
# masked == "請聯絡 <PHONE_1>，身分證 <TW_ID_1>"
restore(masked, vault)  # back to the original
```

## Development

```bash
pip install -e '.[dev]'
pytest
```
