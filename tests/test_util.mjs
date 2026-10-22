import test from "node:test";
import assert from "node:assert/strict";
import { splitCaption, estimateTimeline, fmtTime } from "../assets/template/lib/util.mjs";

test("splitCaption keeps decimal numbers intact", () => {
  const pieces = splitCaption("但计算机给出的是 0.30000000000000004。");
  assert.equal(pieces.length, 1);
  assert.match(pieces[0], /0\.30000000000000004/);
});

test("splitCaption keeps Chinese sentence boundaries when the text is long", () => {
  const text = "这不是 bug，也不是 Python 的锅，更不是语言设计者的失误。是二进制。";
  const pieces = splitCaption(text);
  assert.ok(pieces.length >= 2);
  assert.equal(pieces.join(""), text);
});

test("estimateTimeline is contiguous by default", () => {
  const film = {
    meta: { language: "zh-CN", sceneGap: 0.02 },
    scenes: [
      { id: "a", type: "hook", narration: [{ caption: "第一句。", tts: "第一句。", mark: "one" }] },
      { id: "b", type: "recap", narration: [{ caption: "收尾。", tts: "收尾。", mark: "end" }] },
    ],
  };
  const t = estimateTimeline(film);
  assert.ok(Math.abs(t.scenes[1].start - (t.scenes[0].start + t.scenes[0].duration + 0.02)) < 0.002);
  assert.ok(Math.abs(t.duration - (t.scenes[1].start + t.scenes[1].duration)) < 0.002);
});

test("fmtTime trims trailing zeros", () => {
  assert.equal(fmtTime(2.5), "2.5");
  assert.equal(fmtTime(3), "3");
});
