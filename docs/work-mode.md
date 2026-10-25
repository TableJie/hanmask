# 工作模式

使用者與 Claude 的固定協作方式，由 `CLAUDE.md` 每個 session 自動載入，使用者無須重述。

## 環境

**代號**(只用代號，不加說明):

| 代號 | 指 | | 代號 | 指 |
|---|---|---|---|---|
| cat | 家裡個人電腦 | | fox | 個人 Claude 帳號 |
| dog | 公司公務機 | | wolf | 公司 Claude 帳號 |

| 環境 | 做什麼 | 不做什麼 |
|---|---|---|
| cat | 開發、測試、寫文件、commit、push、開 PR、發布 | 碰真實資料 |
| dog | 從 tag 安裝並跑 proxy,給本機 Claude Code 用；遇到漏遮 / 誤遮用 `/report-miss` | commit、push、登入 `gh`、把真實資料帶出 dog |

- 本機代號寫在 gitignored 的 `CLAUDE.local.md`(範本 `CLAUDE.local.example.md`)。沒有這個檔或不確定 → 直接問使用者。
- **真實資料只在 dog**,只放 `local/`(gitignored)。cat 完全沒有真實資料。
- **回饋方向 dog → cat**:只透過 GitHub Issue(label `from-dog`),內容只有格式相同的合成資料 + 會失敗的 pytest,使用者看過、用瀏覽器送出。流程見 `.claude/skills/report-miss/`。
- 每台各自的狀態(`local/`、`CLAUDE.local.md`、`.claude/error-log.jsonl`、本機 memory)不跨機器；跨機器的事只寫在 repo(`PLAN.md`)或 Issue。

## skill 對照表

| 要做的事 | 用 |
|---|---|
| 拷問計畫 / 改動 | `/grill-me` |
| 收工(cat) | `/coda` |
| 回報漏遮 / 誤遮(dog) | `/report-miss` |
| 審程式改動 | `/code-review` |
| 健檢(死碼 / 重複) | `/review-code` |

## 何時問、何時直接做

1. **交辦範圍內**:直接做到好(含本機 commit),不每步停下問；使用者已明說的事不重複確認。
2. **超出範圍的新功能 / 新類型 / 新設定**:先用一句話提議、等裁決。
3. **決策型問題**(要遮哪些類型、取捨精確率與召回率、擋下或放行):給推薦答案與理由，再讓使用者否決。推薦來自專業判斷，不因「改動最少」就推維持現狀。

## 派 agent

- **該派**:要讀很多檔、互不相關的多件事(平行派)。**自己做**:改一兩個檔、查已知位置、commit / push。
- **模型**(每次明確指定):唯讀文書(整理 PLAN、grep、列清單)用 Haiku;改碼、設計、拷問用 Sonnet;拿不準選 Sonnet。Opus 不自動用。
- **prompt 必含**:
  - 範圍、不改清單、驗證步驟(`pytest` 相關檔);失敗即停並回報原始錯誤。
  - ⛔ 不准還原或改動共用工作樹的 git 指令:`git stash`、`git checkout`、`git reset`、`git clean`、`git restore`、force push。要隔離就用 worktree isolation。
  - ⛔ agent 不 commit / push。
  - ⛔ 被安全機制擋下要停下回報，不換指令繞過。
  - repo 內只准合成個資(`CLAUDE.md` 硬規則)。
- agent 回報「已完成」不直接轉述：自己跑測試、grep 確認。

## 驗證

| 誰 | 什麼時候 | 跑什麼 |
|---|---|---|
| agent | 改完 | 相關的 `pytest` 檔 |
| 主控台 | commit 前 | `pytest -q` |
| 主控台 | push 前(`/coda`) | `pytest`、`python -m bench.run`(漏遮須為 0)、全新 venv 安裝再測、`scripts/sensitive_scan.py --all` |

## commit 與 push

- **commit 訊息與 PR 全部用英文**:祈使句標題(`Add …`、`Fix …`),body 寫為什麼與踩過的 edge case,不寫看 diff 就知道的事。
- **repo 內的文字只寫現況**:文件、註解、commit 不寫「原本是 X、改成 Y」、改名歷史、決策日期;歷史留給 git log。
- **branch + PR**:從 `main` 開 feature branch,完成後 PR 合併(merge commit),合併後刪分支。不直接 commit 到 `main`。
- 大改動落地、測試綠就 commit 存檔點；**push 批次進行**,一批功能完成、`/coda` 全綠才 push。
- **敏感掃描**:`.githooks/pre-commit`(staged 內容)與 `commit-msg`(訊息)跑 `scripts/sensitive_scan.py`,預設 block。每個 clone 啟用一次:`git config core.hooksPath .githooks`。合成資料誤報加進 `scripts/sensitive_scan_allow.json`(路徑 + 規則 + 理由);暫時放行才設 `HANMASK_SCAN_MODE=warn`。
- 一個 commit 一件事，明列路徑(`git commit -- <paths>`)。

## 發布

- 版本號 semver(`pyproject.toml` 的 `version`),tag `vX.Y.Z`(annotated)。
- 發布前在 `CHANGELOG.md` 加一節「這版改了什麼」(面向使用者，3–8 條)。
- 流程:`/coda` 全綠 → 改 `version` 與 `CHANGELOG.md` → commit → `git tag -a vX.Y.Z -m "<摘要>"` → `git push origin main vX.Y.Z`。
- **dog 安裝 / 升級**(dog 要有 repo 才能用 `/report-miss`,所以 clone 而不是只用 pip):

  ```bash
  git clone https://github.com/TableJie/hanmask && cd hanmask   # 第一次
  git fetch --tags && git checkout vX.Y.Z
  python -m venv .venv && .venv/Scripts/python -m pip install .
  ```

## 紅線

- 開 PR、merge、force push、改寫已 push 的 history、建立 GitHub label 或 release:需使用者同意。
- 不 `--no-verify`、不繞過安全機制；被擋下停下回報。
- 真實資料、公司名稱、真實人名不進 repo、不進 Issue、不進 commit 訊息。

## 健檢

- 錯誤紀錄器:`.claude/hooks/error-log.mjs`(PostToolUseFailure)把工具失敗記進 gitignored 的 `.claude/error-log.jsonl`(每台各一份),同 signature 第 3 次起或命中 `.claude/hooks/error-hints.json` 時當場提醒。`/coda` 用 `--report` 列重複錯誤。紀錄只回報 signature、次數、hint,不回貼錯誤原文(dog 上可能含真實資料)。
- 改辨識規則後跑 `python -m bench.run` 比較精確率與漏遮；合成資料只用來比較改版前後，不代表真實準確率。
