// error-log.mjs 的純函數:signature 正規化、預期內失敗判斷、hint 比對、門檻與彙整。
// CLI 殼(讀 stdin / 寫檔)在 ../error-log.mjs,這裡不碰 I/O 方便測試。

const REPEAT_THRESHOLD = 3;

const SHELL_TOOLS = new Set(["Bash", "PowerShell"]);
const EXIT_LINE = /^Exit code \d+\s*$/;
const TRUNCATED_LINE = /^\.\.\. \[\d+ characters truncated\] \.\.\.$/;

/** 第一行 `Exit code N` 是穩定欄位;其餘是顯示文字。 */
function parseExitCode(error) {
  const m = /^Exit code (\d+)/.exec(String(error ?? ""));
  return m ? Number(m[1]) : null;
}

/** 去掉會隨每次執行變動的片段,讓同類錯誤得到同一個字串。 */
export function normalizeLine(line) {
  return String(line)
    .replace(/"[^"\n]*"|'[^'\n]*'|`[^`\n]*`/g, "<s>")
    .replace(/[A-Za-z]:[\\/][^\s:;,)"']*/g, "<path>")
    .replace(/(?:\.{0,2}\/)?(?:[\w@.~-]+\/)+[\w@.~-]*/g, "<path>")
    .replace(/\b[0-9a-f]{7,}\b/gi, "<hex>")
    .replace(/\d+/g, "<n>")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 160);
}

function firstMeaningfulLine(error) {
  for (const raw of String(error ?? "").split(/\r?\n/)) {
    const line = raw.trim();
    if (line && !EXIT_LINE.test(line) && !TRUNCATED_LINE.test(line)) return line;
  }
  return "";
}

/**
 * `git push origin x` → `git push`;`.venv/Scripts/python.exe -m pytest -q` → `python -m pytest`;
 * 其他取第一個字。直譯器路徑只留檔名,不同 venv 才算同一類。
 */
function commandHead(command) {
  const words = String(command ?? "").trim().split(/\s+/).filter(Boolean);
  if (!words.length) return "";
  const first = words[0].split(/[\\/]/).pop().replace(/\.exe$/i, "");
  if (/^python3?$|^py$/.test(first) && words[1] === "-m" && words[2]) return `python -m ${words[2]}`;
  const runners = new Set(["npx", "npm", "node", "git", "gh", "pip", "python", "python3", "py"]);
  return runners.has(first) && words[1] ? `${first} ${words[1]}` : first;
}

export function signatureOf(input) {
  const tool = input?.tool_name ?? "unknown";
  const head = SHELL_TOOLS.has(tool) ? commandHead(input?.tool_input?.command) : "";
  const code = parseExitCode(input?.error);
  const line = normalizeLine(firstMeaningfulLine(input?.error)) || (code !== null ? "exit <n>" : "");
  return [tool, head, line].filter(Boolean).join(" | ");
}

/** grep / rg 沒找到(exit 1、無輸出)屬預期內,不算錯誤。 */
export function isExpectedFailure(input) {
  const tool = input?.tool_name;
  if (tool === "Grep") return true;
  if (!SHELL_TOOLS.has(tool)) return false;
  const first = String(input?.tool_input?.command ?? "").trim().split(/\s+/)[0] ?? "";
  return /^(grep|rg|egrep|fgrep)$/.test(first) && String(input?.error ?? "").trim() === "Exit code 1";
}

export function shouldSkip(input) {
  return !input || input.is_interrupt === true || isExpectedFailure(input);
}

/** 命中第一條 hint(match 為正則字串,壞正則略過)。 */
export function matchHint(hints, errorText) {
  if (!Array.isArray(hints)) return null;
  for (const h of hints) {
    if (!h || typeof h.match !== "string" || typeof h.hint !== "string") continue;
    try {
      if (new RegExp(h.match, "i").test(errorText)) return h;
    } catch {
      // 壞正則不讓紀錄器失敗
    }
  }
  return null;
}

export function countSignature(records, signature) {
  return records.reduce((n, r) => n + (r.signature === signature ? 1 : 0), 0);
}

/** 回給 Claude 的提醒;只含 signature、次數、hint,不回貼 error 原文(可能含真實資料)。 */
export function buildContext({ hint, count, signature, threshold = REPEAT_THRESHOLD }) {
  if (hint) return `[錯誤紀錄器] 已知問題(${hint.id ?? "hint"}):${hint.hint}`;
  if (count >= threshold) {
    return `[錯誤紀錄器] 這類錯誤(${signature})已發生 ${count} 次,先想清楚根因再重試,不要重跑同一個指令。`;
  }
  return null;
}

/** 台灣時間 "YYYY-MM-DDTHH:mm:ss":--since 用台灣日期篩,UTC 會把早上 8 點前的錯誤算到前一天。 */
export function taipeiStamp(date = new Date()) {
  return date.toLocaleString("sv-SE", { timeZone: "Asia/Taipei", hour12: false }).replace(" ", "T");
}

/** 依 signature 彙整:次數、總耗時、最近一次、是否已有 hint。 */
export function summarize(records, hints, since) {
  const bySig = new Map();
  for (const r of records) {
    const ts = String(r.ts ?? "");
    if (since && ts < since) continue;
    const s = bySig.get(r.signature) ?? { signature: r.signature, count: 0, totalMs: 0, last: "", hint: null };
    s.count += 1;
    s.totalMs += Number(r.duration_ms) || 0;
    if (ts >= s.last) s.last = ts;
    s.hint ??= matchHint(hints, String(r.error ?? ""))?.id ?? null;
    bySig.set(r.signature, s);
  }
  return [...bySig.values()].sort((a, b) => b.count - a.count || b.totalMs - a.totalMs);
}

export function formatReport(rows) {
  if (!rows.length) return "沒有錯誤紀錄。";
  return rows
    .map((r) => `${String(r.count).padStart(3)} 次  ${(r.totalMs / 1000).toFixed(1)}s  最近 ${r.last.slice(0, 16)}  ${r.hint ? `[hint:${r.hint}]` : "[無 hint]"}  ${r.signature}`)
    .join("\n");
}
