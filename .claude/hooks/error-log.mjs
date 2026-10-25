// PostToolUseFailure hook:把工具失敗記進 .claude/error-log.jsonl(gitignored、每台各一份),
// 同類錯誤累計 >= 3 次或命中 error-hints.json 時,把提醒回給 Claude。
// 用法:hook 模式讀 stdin JSON;`node .claude/hooks/error-log.mjs --report [--since YYYY-MM-DD]` 列彙整。
// error-hints.json 格式(JSON 不能註解,故寫在這裡):
//   [{ "id": "venv-missing", "match": "No module named '?hanmask", "hint": "用 .venv/Scripts/python 執行,或先 pip install -e '.[dev]'" }]
//   match 是對 error 全文的正則(不分大小寫);hint 只寫通用解法,不貼錯誤原文。
// 紀錄含 error 前 500 字(dog 可能有真實資料),所以回給 Claude 的內容只有 signature、次數、hint。
// 環境變數 ERROR_LOG_PATH / ERROR_HINTS_PATH 可改路徑(測試用)。任何例外一律 exit 0 且不輸出。
import { appendFileSync, existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { buildContext, countSignature, formatReport, matchHint, shouldSkip, signatureOf, summarize, taipeiStamp } from "./lib/error-log-core.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const LOG = process.env.ERROR_LOG_PATH || join(here, "..", "error-log.jsonl");
const HINTS = process.env.ERROR_HINTS_PATH || join(here, "error-hints.json");

function readJson(path, fallback) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return fallback;
  }
}

function readLog() {
  if (!existsSync(LOG)) return [];
  const out = [];
  for (const line of readFileSync(LOG, "utf8").split("\n")) {
    if (!line.trim()) continue;
    try {
      out.push(JSON.parse(line));
    } catch {
      // 壞行略過
    }
  }
  return out;
}

function report(argv) {
  const i = argv.indexOf("--since");
  const since = i >= 0 ? argv[i + 1] : undefined;
  console.log(formatReport(summarize(readLog(), readJson(HINTS, []), since)));
}

async function hook() {
  let raw = "";
  for await (const chunk of process.stdin) raw += chunk;
  const input = JSON.parse(raw);
  if (shouldSkip(input)) return;
  const signature = signatureOf(input);
  const error = String(input.error ?? "");
  const ti = input.tool_input ?? {};
  const record = {
    ts: taipeiStamp(),
    session: input.session_id,
    agent_type: input.agent_type,
    tool: input.tool_name,
    target: String(ti.command ?? ti.file_path ?? ti.path ?? ti.pattern ?? "").slice(0, 200),
    error: error.slice(0, 500),
    duration_ms: input.duration_ms,
    signature,
  };
  const count = countSignature(readLog(), signature) + 1;
  appendFileSync(LOG, JSON.stringify(record) + "\n");
  const context = buildContext({ hint: matchHint(readJson(HINTS, []), error), count, signature });
  if (context) {
    console.log(JSON.stringify({ hookSpecificOutput: { hookEventName: "PostToolUseFailure", additionalContext: context } }));
  }
}

try {
  if (process.argv.includes("--report")) report(process.argv);
  else await hook();
} catch {
  // 紀錄器不能讓工作失敗
}
process.exit(0);
