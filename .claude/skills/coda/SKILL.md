---
name: coda
description: 收工(coda,cat 用)——把這段工作收尾：拷問這批改動、pytest + bench、全新 venv 安裝再測一次、列出未關的 from-dog Issue、問題一次問完，綠燈才 push。使用者說「今天結束」「收工」「下班」「coda」時使用。一天可能說好幾次、說完還會繼續做，所以只處理增量，重複執行也安全。
---

# 收工(coda)

說「收工」≠ 關 session:收尾後可以繼續工作，下次再說就只處理新的增量。

## 進度清單(複製到回覆逐項打勾)

```
- [ ] 1. 定範圍(沒有增量就結束)
- [ ] 2. commit 未提交改動
- [ ] 3. 同時跑：拷問 + 測試 + 全新 venv + 掃描 + PLAN 整理 + from-dog Issue + 重複錯誤
- [ ] 4. 一次問完
- [ ] 5. 收尾：處理回答 → 重跑檢查 → push
- [ ] 6. 回報
```

## 1. 定範圍

- 環境看 `CLAUDE.local.md`。不是 cat → 停下:dog 不 commit、不 push(`docs/work-mode.md`「環境」)。
- 先 `git fetch`;失敗(離線)→ 停下回報、不 push,不拿舊的 origin 算範圍。目前分支落後 origin → 停下回報，不自動 pull / merge。
- 範圍 = `git log origin/main..HEAD`(這個分支還沒進 main 的 commit)+ `git status` 的未提交改動。
- 範圍為空 → 回一句「上次收工後沒有新改動」,結束。

## 2. commit 未提交改動

照 `docs/work-mode.md`「commit 與 push」:依主題分 commit、`git commit -- <paths>`、先 `git diff --cached --name-only` 確認。歸屬判斷不了的不 commit,放進第 4 步。

## 3. 同時跑(能平行就平行)

**a. 拷問**(派子 agent,Sonnet,唯讀):照 `.claude/skills/grill-me/SKILL.md` 的「先找前提錯誤」與「hanmask 的五種失效」審範圍內的 commit。agent 只回報問題與推薦答案，不問使用者；題目併入第 4 步，排最前面。

**b. 測試**(每個指令單獨跑):
- `.venv/Scripts/python -m pytest -q`
- `.venv/Scripts/python -m bench.run --n 2000`(有 `bench/` 時):`leaked` 必須是 0;精確率比上次低要列進第 4 步
- `node --test .claude/hooks/lib/error-log-core.test.mjs`(範圍有動 `.claude/hooks/` 時)

**c. 全新 venv**:dog 是從零安裝，這一步抓漏寫的依賴與沒進 git 的檔案。只裝已 commit 的內容:

```bash
tmp=$(mktemp -d)
git archive HEAD | tar -x -C "$tmp"
(cd "$tmp" && python -m venv venv \
  && venv/Scripts/python -m pip install -q . \
  && venv/Scripts/python -c "import hanmask" \
  && venv/Scripts/python -m pip install -q ".[dev]" \
  && venv/Scripts/python -m pytest -q)
rm -rf "$tmp"
```

先裝不含 dev 的版本再 import:dog 拿到的就是這個。在 `$tmp` 裡用相對路徑安裝，因為 Windows 的 pip 不認得 Git Bash 的 `/tmp/...[dev]`。非 Windows 把 `Scripts` 換成 `bin`。

**d. 敏感掃描**:`.venv/Scripts/python scripts/sensitive_scan.py --all` 須零命中。命中 → 不 push,回報檔案與規則，不貼命中內容。順便確認 `git config core.hooksPath` 是 `.githooks`。

**e. 整理 `PLAN.md`**(派 Haiku):完成的打勾、對話中「之後再做」的加進對應里程碑、決策寫進「已決定」;只寫現況，不寫「原本 / 改成」。

**f. from-dog Issue**:`gh issue list --label from-dog --state open`。每條列出標題與編號；範圍內的 commit 已修好的，提案「關閉並附 commit」,併入第 4 步。

**g. 重複錯誤**:`node .claude/hooks/error-log.mjs --report --since <今天 YYYY-MM-DD>`。同一 signature >= 3 次且「無 hint」的，每條提案「加 hint(`.claude/hooks/error-hints.json`)/ 寫測試 / 寫進 `docs/work-mode.md` / 忽略」,併入第 4 步。不要把 `.claude/error-log.jsonl` 的內容貼進任何檔案或回報。

## 4. 一次問完

把第 2、3 步所有待裁決事項(拷問的排最前面)合成**一次**提問，用 grill-me 的格式(編號、附推薦答案、「是」= 接受推薦)。固定加兩題：
- 「有沒有還在調整、先不要 push 的改動?」
- 「這個分支要不要現在開 PR?」(開 PR 需同意，見 `docs/work-mode.md`「紅線」)

## 5. 收尾

1. 依回答處理(要修的修、記 PLAN 的派 Haiku 寫進去、要關的 Issue 用 `gh issue close <n> -c "<commit>"`)。
2. 第 3 步之後有新的程式 commit → 重跑 3b、3d。
3. 全綠 → `git push -u origin <目前分支>`;使用者同意才開 PR。
4. 紅燈 / 掃描命中 / 被安全機制擋下 → 不 push、不繞過(不 `--no-verify`、不 force push),回報原始錯誤。

## 6. 回報

結果先行：
- push 了哪些 commit(或沒 push 與原因)、PR 連結
- 測試、bench(精確率 / 漏遮)、全新 venv、掃描的結果
- PLAN 勾選 / 新增了什麼、關了哪些 from-dog Issue
- 之後第一步(一個兩分鐘內能開始的動作)
