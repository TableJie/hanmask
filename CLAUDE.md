@docs/work-mode.md

# hanmask

自架的 LLM 代理服務：個資在送出前遮蔽成佔位符，回應回來時還原。Python 3.10+,核心只用標準函式庫。公開 repo,Apache-2.0。進度與決策見 `PLAN.md`。

## 分流 — 要做什麼 → 先讀哪個檔

| 要做的事 | 先讀 |
|---|---|
| 改辨識規則、加個資類型 | `hanmask/recognizers.py` + `tests/test_recognizers.py`;改完跑 `python -m bench.run` |
| 遮蔽 / 還原 / 串流 | `hanmask/masker.py`、`hanmask/streaming.py` |
| 進度、待辦、已決定事項 | `PLAN.md` |
| 環境(cat / dog)、commit、PR、發布、派 agent | `docs/work-mode.md`(已自動載入) |
| 收工 | `/coda` |
| dog 回報漏遮 / 誤遮 | `/report-miss` |
| 敏感掃描誤報 | `scripts/sensitive_scan_allow.json` |

## 硬規則

- **repo 內只准合成個資**:測試與範例的身分證、統編、卡號一律合成或公開測試值；不出現公司名稱、真實人名、內部路徑或 IP。由 `scripts/sensitive_scan.py`(pre-commit)把關。
- **真實資料只在 dog 的 `local/`**,不進 git、不進 Issue、不進對話以外的任何地方。dog → cat 只走 `from-dog` Issue(合成資料 + 會失敗的 pytest)。
- **文字只寫現況**:文件、註解、commit 不寫「原本 / 改成」、改名歷史、決策日期。
- **commit 訊息與 PR 用英文**(`docs/work-mode.md`「commit 與 push」)。
- **測試先行**:改辨識規則一定附測試，含「不該遮」的反例。

## 常用指令

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -e '.[dev]'
git config core.hooksPath .githooks              # 每個 clone 一次
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m bench.run --n 2000       # 合成資料量測
.venv/Scripts/python scripts/sensitive_scan.py --all
node --test .claude/hooks/lib/error-log-core.test.mjs
```

Windows 印中文時加 `PYTHONIOENCODING=utf-8`。
