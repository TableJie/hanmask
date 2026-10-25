// node --test .claude/hooks/lib/error-log-core.test.mjs
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { buildContext, countSignature, isExpectedFailure, matchHint, normalizeLine, shouldSkip, signatureOf, summarize, taipeiStamp } from "./error-log-core.mjs";

const bash = (command, error, extra = {}) => ({ tool_name: "Bash", tool_input: { command }, error, ...extra });

describe("signatureOf", () => {
  it("數字、路徑、引號內字串不影響 signature", () => {
    const a = signatureOf(bash("python -m pytest -q", "Exit code 1\ntests/test_a.py:12: AssertionError: 'foo'"));
    const b = signatureOf(bash("python -m pytest tests/x", "Exit code 1\ntests/test_b.py:99: AssertionError: 'bar'"));
    assert.equal(a, b);
    assert.ok(a.startsWith("Bash | python -m pytest | "));
  });
  it("venv 路徑與 .exe 不影響指令類別", () => {
    const a = signatureOf(bash(".venv/Scripts/python.exe -m pytest -q", "Exit code 1\nboom"));
    const b = signatureOf(bash("python -m pytest", "Exit code 1\nboom"));
    assert.equal(a, b);
  });
  it("不同指令不撞同一 signature", () => {
    assert.notEqual(signatureOf(bash("git push", "Exit code 1\nboom")), signatureOf(bash("node x.js", "Exit code 1\nboom")));
  });
  it("只有 Exit code 時仍有 signature", () => {
    assert.equal(signatureOf(bash("node -e x", "Exit code 1")), "Bash | node -e | exit <n>");
  });
  it("路徑與 hex 雜湊被正規化", () => {
    assert.equal(normalizeLine("ENOENT /tmp/a/b.txt at deadbeef01"), "ENOENT <path> at <hex>");
  });
  it("壞輸入不丟錯", () => {
    assert.doesNotThrow(() => signatureOf(undefined));
    assert.doesNotThrow(() => signatureOf({ tool_name: "Bash", error: 5 }));
  });
});

describe("shouldSkip", () => {
  it("is_interrupt 與壞輸入略過", () => {
    assert.equal(shouldSkip(bash("x", "Exit code 1\nz", { is_interrupt: true })), true);
    assert.equal(shouldSkip(null), true);
  });
  it("Grep 工具與 grep/rg 的空結果 exit 1 屬預期", () => {
    assert.equal(isExpectedFailure({ tool_name: "Grep", error: "x" }), true);
    assert.equal(isExpectedFailure(bash("rg foo src", "Exit code 1")), true);
    assert.equal(isExpectedFailure(bash("grep -r foo .", "Exit code 2\nNo such file")), false);
    assert.equal(isExpectedFailure(bash("python -m pytest", "Exit code 1")), false);
  });
});

describe("hint 與門檻", () => {
  const hints = [
    { id: "bad", match: "(", hint: "x" },
    { id: "h1", match: "No module named", hint: "先 pip install" },
  ];
  it("命中 hint,壞正則不丟錯", () => {
    assert.equal(matchHint(hints, "ModuleNotFoundError: No module named 'x'")?.id, "h1");
    assert.equal(matchHint(hints, "other"), null);
    assert.equal(matchHint(undefined, "x"), null);
  });
  it("第 3 次起才提醒,內容不含 error 原文", () => {
    assert.equal(buildContext({ count: 2, signature: "s" }), null);
    assert.match(buildContext({ count: 3, signature: "s" }), /3 次/);
    assert.match(buildContext({ hint: hints[1], count: 1, signature: "s" }), /先 pip install/);
  });
  it("countSignature 與 summarize", () => {
    const rs = [
      { signature: "a", ts: "2026-10-24T01:00", duration_ms: 1000, error: "No module named x" },
      { signature: "a", ts: "2026-10-25T01:00", duration_ms: 500, error: "No module named x" },
      { signature: "b", ts: "2026-10-25T02:00", duration_ms: 10, error: "z" },
    ];
    assert.equal(countSignature(rs, "a"), 2);
    const top = summarize(rs, hints)[0];
    assert.deepEqual([top.signature, top.count, top.totalMs, top.hint], ["a", 2, 1500, "h1"]);
    assert.deepEqual(summarize(rs, hints, "2026-10-25").map((r) => [r.signature, r.count]), [["a", 1], ["b", 1]]);
  });
  it("taipeiStamp 用台灣時區(UTC 前一天 23:30 = 台灣隔天 07:30)", () => {
    assert.equal(taipeiStamp(new Date("2026-10-24T23:30:00Z")), "2026-10-25T07:30:00");
  });
});
