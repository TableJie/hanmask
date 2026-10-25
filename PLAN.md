# hanmask 開發計畫

來源：Claude Docs《去識別化閘道 開源計畫書》。

## 目標（MVP）

讓呼叫 Claude 或 OpenAI 的程式只要改 `base_url`，就能自動遮蔽並還原中英文個資。時程以每天約 8 小時估算：總共約 15 個工作天，加上 5 天緩衝，目標 4 週內發表。

## 架構

```
client ──► hanmask proxy ──► LLM API
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
| `hanmask/recognizers.py` | 正規表示式＋檢查碼的規則辨識器 | ✅ 已完成 |
| `hanmask/masker.py` | `Masker`、`Vault`、`restore()`：可逆遮蔽 | ✅ 已完成 |
| `hanmask/streaming.py` | `StreamRestorer`：處理被切在兩個片段之間的佔位符 | ✅ 已完成 |
| `hanmask/sensitive.py` | 特種個資偵測，嚴格模式擋下 | ✅ 已完成 |
| `bench/` | 合成資料（含 HR、AR、行銷情境）與準確率量測 | ✅ 已完成 |
| `hanmask/proxy/` | FastAPI：OpenAI `/v1/chat/completions`、Anthropic `/v1/messages`，含 SSE | ⏳ 第 3–6 天 |
| `hanmask/ner.py` | 本地 NER：中文姓名、無後綴的公司名稱 | ⏳ 第 7–10 天 |
| `hanmask/audit.py`、`config.py` | SQLite 稽核日誌、YAML 設定 | ⏳ 第 11–12 天 |
| `Dockerfile`、README、測試資料集 | 包裝與發表 | ⏳ 第 13–15 天 |

## 里程碑與待辦

### 第 1–2 天：規則式辨識
- [x] 台灣身分證／新式居留證（含檢查碼）
- [x] 統一編號（含檢查碼，2023 年後「可被 5 整除」規則）
- [x] 手機、市話（含 `+886`、`(02)` 格式）
- [x] Email
- [x] 信用卡號（Luhn）
- [x] 重疊處理：較長者優先，同長度比優先順序
- [x] 中文字緊貼數字時仍能辨識（ASCII lookaround）
- [x] 同一請求內，相同原文對應同一佔位符
- [x] 串流還原的緩衝邏輯
- [x] 舊式居留證（第二碼為英文字母）
- [x] 全形數字與英文（`０９１２－３４５－６７８`），還原時保留全形寫法
- [x] 繁體中文 README（`README.zh-TW.md`）
- [x] 護照號碼、健保卡號、銀行帳號：以前方關鍵字把關（同一子句、20 字內）
- [x] 合成資料量測準確率與誤判率：`python -m bench.run`
- [x] 企業識別碼：訂單、發票、料號、其他編號、公司名稱（法定後綴）
- [x] HR、AR、行銷情境：地址、生日、薪資、IP、UUID、社群帳號
- [x] 特種個資（醫療、健檢、基因、性生活、前科）：`Masker(strict=True)` 擋下
- [ ] 「戶名：大華科技」這類沒有法定後綴的戶名

### 第 3–6 天：proxy 與還原
- [ ] FastAPI 骨架，上游 URL 與 API key 從環境變數讀取
- [ ] OpenAI 格式：遮蔽 `messages[].content`（字串與 content parts 兩種）
- [ ] Anthropic 格式：遮蔽 `system` 與 `messages[].content`
- [ ] 非串流回應還原
- [ ] SSE 串流還原：每個 content delta 交給 `StreamRestorer`，結束時 `flush()`
- [ ] tool call 參數裡的佔位符也要還原（JSON 字串內）
- [ ] Anthropic `tool_result` 內容也要遮蔽（Claude Code 讀檔、執行指令的結果都放在這裡）
- [ ] 圖片與 PDF（base64 的 `image`、`document` 區塊）無法用文字規則遮蔽：要決定放行、擋下或抽文字
- [ ] 整合測試：用假的上游伺服器驗證整條路徑

### 第 7–10 天：中文姓名
- [ ] 選定本地 NER 模型（不採用中國開發的模型），實測中文姓名準確率
- [ ] 規則抓不到的才交給模型（姓名、無後綴的公司名稱、不完整的地址）

### 第 11–12 天：稽核日誌與設定
- [ ] SQLite：時間、目標模型、各類型遮蔽筆數（`Vault.counts()`），不存原文
- [ ] YAML：啟用哪些類型、嚴格模式開關

### 第 13–15 天：包裝與發表
- [ ] `docker run` 一行啟動
- [ ] GIF demo、英文與中文 README
- [ ] 至少 500 筆合成中文測試資料＋與 Presidio 的準確率對照表

## 已決定

- **專案名稱**：hanmask（han = 漢字），PyPI 與 GitHub 上無同名專案。
- **投入時間**：每天約 8 小時，時程以工作天計。
- **授權條款**：Apache-2.0（含專利授權條款，企業採用較放心），見 `LICENSE`。
- **關鍵字判斷順序**：正向關鍵字 → 必要關鍵字（護照、健保卡、銀行帳號）→ 企業識別碼標籤（訂單、料號等，不當成個資）→ 格式與檢查碼。
- **企業識別碼**：`ORDER_NO`、`INVOICE_NO`、`PART_NO`、`REF_NO`、`ORG_NAME` 預設遮蔽，`Masker(enabled=PII_TYPES)` 可只遮個資。
- **金額**：只遮薪資（前方有月薪、年薪、獎金等），應收、發票等金額保留給 LLM 分析。
- **特種個資**：嚴格模式下整筆請求擋下，不嘗試遮蔽；錯誤只帶類別名稱。
- **適用範圍**：只涵蓋走公開 API 的程式（SDK、Claude Code 設定 `ANTHROPIC_BASE_URL`）。Claude Desktop 與 claude.ai 網頁版連的是 claude.ai 自己的後端，無法改 `base_url`，不在範圍內。
- **公司智慧財產權**：公司沒有限制員工業餘開發的相關規定。程式碼與測試資料仍不放任何公司內容。

## 開發

```bash
pip install -e '.[dev]'
pytest
```
