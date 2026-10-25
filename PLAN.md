# maskgate 開發計畫

來源：Claude Docs《去識別化閘道 開源計畫書》。文件裡的暫名是 Veil，repo 名稱目前是 `maskgate`，兩者擇一前先統一用 `maskgate`。

## 目標（MVP）

讓呼叫 Claude 或 OpenAI 的程式只要改 `base_url`，就能自動遮蔽並還原中英文個資。時程以每天約 8 小時估算：總共約 15 個工作天，加上 5 天緩衝，目標 4 週內發表。

## 架構

```
client ──► maskgate proxy ──► LLM API
            │ 1. 辨識個資（規則 → NER）
            │ 2. 換成 <TYPE_n> 佔位符，對照表存在記憶體（Vault）
            │ 3. 轉送給上游
            │ 4. 回應（含串流）把佔位符換回原文
            │ 5. 稽核日誌只記類型與數量，不存原文
            ▼
          請求結束，Vault 丟棄
```

模組規劃：

| 模組 | 職責 | 狀態 |
|---|---|---|
| `maskgate/recognizers.py` | 正規表示式＋檢查碼的規則辨識器 | ✅ 已完成 |
| `maskgate/masker.py` | `Masker`、`Vault`、`restore()`：可逆遮蔽 | ✅ 已完成 |
| `maskgate/streaming.py` | `StreamRestorer`：處理被切在兩個片段之間的佔位符 | ✅ 已完成 |
| `maskgate/proxy/` | FastAPI：OpenAI `/v1/chat/completions`、Anthropic `/v1/messages`，含 SSE | ⏳ 第 3–6 天 |
| `maskgate/ner.py` | 本地 NER：中文姓名、地址 | ⏳ 第 7–10 天 |
| `maskgate/audit.py`、`config.py` | SQLite 稽核日誌、YAML 設定 | ⏳ 第 11–12 天 |
| `Dockerfile`、README、測試資料集 | 包裝與發表 | ⏳ 第 13–15 天 |

## 里程碑與待辦

### 第 1–2 天：規則式辨識（已做好基礎）
- [x] 台灣身分證／新式居留證（含檢查碼）
- [x] 統一編號（含檢查碼，2023 年後「可被 5 整除」規則）
- [x] 手機、市話（含 `+886`、`(02)` 格式）
- [x] Email
- [x] 信用卡號（Luhn）
- [x] 重疊處理：較長者優先，同長度比優先順序
- [x] 中文字緊貼數字時仍能辨識（不用 `\b`，改用 ASCII lookaround）
- [x] 同一請求內，相同原文對應同一佔位符
- [x] 串流還原的緩衝邏輯
- [ ] 舊式居留證（第二碼為英文字母）
- [ ] 護照號碼、健保卡號、銀行帳號：要先評估誤判率
- [ ] 用合成資料量測準確率與誤判率

### 第 3–6 天：proxy 與還原
- [ ] FastAPI 骨架，上游 URL 與 API key 從環境變數讀取
- [ ] OpenAI 格式：遮蔽 `messages[].content`（字串與 content parts 兩種）
- [ ] Anthropic 格式：遮蔽 `system` 與 `messages[].content`
- [ ] 非串流回應還原
- [ ] SSE 串流還原：每個 content delta 交給 `StreamRestorer`，結束時 `flush()`
- [ ] tool call 參數裡的佔位符也要還原（JSON 字串內）
- [ ] 整合測試：用假的上游伺服器驗證整條路徑

### 第 7–10 天：中文姓名與地址
- [ ] 選定本地 NER 模型（避開中國開發的模型），實測中文姓名準確率
- [ ] 規則抓不到的才交給模型
- [ ] 嚴格模式：可疑內容直接擋下

### 第 11–12 天：稽核日誌與設定
- [ ] SQLite：時間、目標模型、各類型遮蔽筆數（`Vault.counts()`），不存原文
- [ ] YAML：啟用哪些類型、嚴格模式開關

### 第 13–15 天：包裝與發表
- [ ] `docker run` 一行啟動
- [ ] GIF demo、英文與中文 README
- [ ] 至少 500 筆合成中文測試資料＋與 Presidio 的準確率對照表

## 待你決定

1. **專案名稱**：Veil 還是 maskgate？要確認 GitHub 與 PyPI 名稱沒被佔用。

## 已決定

- **投入時間**：每天約 8 小時，時程改以工作天計。
- **授權條款**：Apache-2.0（含專利授權條款，企業採用較放心），見 `LICENSE`。
- **公司智慧財產權**：公司沒有限制員工業餘開發的相關規定。程式碼與測試資料仍不放任何公司內容。

## 開發

```bash
pip install -e '.[dev]'
pytest
```
