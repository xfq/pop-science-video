#!/usr/bin/env node
// Turn film.json (+ measured timeline.json) into a renderable HyperFrames project.
// All content is baked into static HTML: the renderer never fetches data at render time.
import fs from "node:fs";
import path from "node:path";
import { SCENES } from "./lib/scenes.mjs";
import { baseCss, fontFaces, THEME } from "./lib/theme.mjs";
import { esc, estimateTimeline, pad2, sceneTimeline, slug, splitCaption, fmtTime } from "./lib/util.mjs";

const ROOT = process.cwd();
const FILM = path.join(ROOT, "film.json");
const TIMELINE = path.join(ROOT, "timeline.json");
const COMPOSITIONS = path.join(ROOT, "compositions");
const warnings = [];

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

if (!fs.existsSync(FILM)) {
  console.error("film.json not found. Run this from the project root, or copy assets/template first.");
  process.exit(2);
}

const film = readJson(FILM);
const meta = film.meta || {};
const width = Number(meta.width || 1920);
const height = Number(meta.height || 1080);
const fps = Number(meta.fps || 30);
if (width !== 1920 || height !== 1080) {
  warnings.push(`This template is authored for 1920x1080; got ${width}x${height}. Scene layouts may not fit.`);
}
if (!Array.isArray(film.scenes) || film.scenes.length === 0) {
  console.error("film.json has no scenes.");
  process.exit(2);
}

const timeline = fs.existsSync(TIMELINE) ? readJson(TIMELINE) : estimateTimeline(film);
if (!timeline.scenes || timeline.scenes.length !== film.scenes.length) {
  console.error("timeline.json does not match the scene count in film.json. Re-run scripts/make_timeline.py.");
  process.exit(2);
}
if (!timeline.captions || timeline.captions.length === 0) {
  timeline.captions = [];
  film.scenes.forEach((scene, si) => {
    const tl = sceneTimeline(timeline, scene.id, si);
    (scene.narration || []).forEach((line) => {
      const start = tl.chunks.find((c) => c.caption === (line.caption || line.tts))?.start ?? tl.start;
      for (const piece of splitCaption(line.caption || line.tts || "")) {
        timeline.captions.push({ text: piece, start, dur: 2 });
      }
    });
  });
}

fs.mkdirSync(COMPOSITIONS, { recursive: true });
for (const scene of film.scenes) {
  if (!SCENES[scene.type]) {
    console.error(`Unknown scene type "${scene.type}" (scene ${scene.id}). Known: ${Object.keys(SCENES).join(", ")}`);
    process.exit(2);
  }
}

const total = Number(timeline.duration.toFixed(3));
const sceneFiles = [];

function sceneJs(scene, tl, index) {
  const marks = { ...(tl.marks || {}) };
  const revealMarks = new Set();
  const html = scene.__html || "";
  for (const m of html.matchAll(/data-reveal="([^"]+)"/g)) {
    for (const one of m[1].split(/\s+/)) if (one) revealMarks.add(one);
  }
  let fallback = 0.25;
  for (const mark of revealMarks) {
    if (!(mark in marks)) {
      marks[mark] = fallback;
      warnings.push(`[${scene.id}] mark "${mark}" has no narration timing; placed at ${fallback.toFixed(2)}s.`);
      fallback += 0.35;
    }
  }
  const entries = Object.entries(marks).sort((a, b) => a[1] - b[1]);
  const lines = [];
  lines.push(`const tl = gsap.timeline({ paused: true });`);
  lines.push(`const ID = ${JSON.stringify(scene.id)};`);
  lines.push(`const FIRST = ${index === 0 ? "true" : "false"};`);
  lines.push(`if (FIRST) { gsap.set("[data-reveal], [data-intro]", { opacity: 1 }); }`);
  for (const [mark, time] of entries) {
    const sel = `[data-reveal~="${mark.replaceAll('"', '\\"')}"]`;
    lines.push(`animate(${JSON.stringify(sel)}, ${Math.max(0, Number(time) - Number(tl.start || 0)).toFixed(3)});`);
  }
  lines.push(`animate("[data-intro]", 0.06, true);`);
  // Any reveal that could not be timed is shown early instead of staying invisible.
  lines.push(`if (!FIRST) { gsap.utils.toArray("[data-reveal]").forEach((el) => { if (Number(el.dataset.shown || 0) === 0) { el.dataset.shown = "1"; gsap.set(el, { opacity: 1 }); } }); }`);
  lines.push(`
function animate(selector, at, intro) {
  const els = gsap.utils.toArray(selector);
  els.forEach((el, i) => {
    if (el.dataset.shown === "1") return;
    el.dataset.shown = "1";
    const anim = el.dataset.anim || "";
    const delay = at + i * 0.055;
    if (FIRST) {
      if (anim === "grow-x") tl.fromTo(el, { scaleX: 0 }, { scaleX: 1, duration: 0.9, ease: "power3.inOut" }, delay);
      else if (anim === "pulse") tl.fromTo(el, { scale: 1.035 }, { scale: 1, duration: 0.6, ease: "power3.out" }, delay);
      else tl.fromTo(el, { y: 14, opacity: 1 }, { y: 0, opacity: 1, duration: 0.62, ease: "power3.out" }, delay);
      return;
    }
    if (anim === "grow-x") {
      tl.fromTo(el, { scaleX: 0, opacity: 0 }, { scaleX: 1, opacity: 1, duration: 0.85, ease: "power3.inOut" }, delay);
    } else if (anim === "pulse") {
      tl.fromTo(el, { scale: 0.94, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.55, ease: "power3.out" }, delay);
    } else if (anim === "type") {
      tl.fromTo(el, { clipPath: "inset(0 100% 0 0)", opacity: 1 }, { clipPath: "inset(0 0% 0 0)", duration: 0.5 + Math.min(0.8, (el.textContent || "").length * 0.018), ease: "steps(24)" }, delay);
    } else if (anim === "stamp") {
      tl.fromTo(el, { scale: 1.35, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.55, ease: "back.out(1.8)" }, delay);
    } else if (anim === "wipe") {
      tl.fromTo(el, { clipPath: "inset(0 100% 0 0)", opacity: 1 }, { clipPath: "inset(0 0% 0 0)", duration: 0.7, ease: "power3.inOut" }, delay);
    } else if (intro) {
      // Intro chrome is already visible at the cut; move it, don't fade it in from black.
      tl.fromTo(el, { opacity: 1, y: 18 }, { opacity: 1, y: 0, duration: 0.55, ease: "power3.out" }, delay);
    } else {
      tl.fromTo(el, { opacity: 0, y: 34 }, { opacity: 1, y: 0, duration: 0.62, ease: "power3.out" }, delay);
    }
  });
}

// Slow, finite background drift. Never uses a render-time clock or Math.random.
const drift = ${Math.max(0, Number(tl.duration) - 0.6)};
gsap.utils.toArray("[data-float]").forEach((el, i) => {
  const cycle = 5.2;
  const repeats = Math.max(0, Math.floor(drift / cycle) - 1);
  tl.to(el, { y: i % 2 ? 10 : -10, duration: cycle / 2, ease: "sine.inOut", yoyo: true, repeat: repeats * 2 }, 0.2);
});
window.__timelines[ID] = tl;
`);
  return lines.join("\n");
}

function subComp(scene, ctx, css, html, js) {
  const id = scene.id;
  return `<!doctype html>
<html lang="${esc(meta.language || "zh-CN")}">
<head><meta charset="UTF-8"><meta name="viewport" content="width=${width}, height=${height}"><title>${esc(scene.id)} · ${esc(meta.title || "CS explainer")}</title></head>
<body>
<template>
<style>
${baseCss()}
${css}
[data-reveal],[data-intro]{opacity:${ctx.index === 0 ? "1" : "0"}}
</style>
<div id="root" data-composition-id="${esc(id)}" data-width="${width}" data-height="${height}">
${html}
</div>
<script>
${js}
</script>
</template>
</body>
</html>`;
}

film.scenes.forEach((scene, index) => {
  const tl = sceneTimeline(timeline, scene.id, index);
  if (!tl) {
    console.error(`timeline.json has no entry for scene "${scene.id}"`);
    process.exit(2);
  }
  const ctx = { scene, index, total: film.scenes.length, tl, film };
  const rendered = SCENES[scene.type](ctx);
  scene.__html = rendered.html;
  const js = sceneJs(scene, tl, index);
  const file = `${pad2(index + 1)}-${slug(scene.id)}.html`;
  fs.writeFileSync(path.join(COMPOSITIONS, file), subComp(scene, ctx, rendered.css, rendered.html, js), "utf8");
  sceneFiles.push({ id: scene.id, file, type: scene.type, start: tl.start, duration: tl.duration });
  delete scene.__html;
});

// ---------------------------------------------------------------- captions
let captionsHost = "";
let captionFile = null;
if (timeline.captions.length) {
  captionFile = "compositions/captions.html";
  const caps = timeline.captions.map((c, i) => `<div class="cap" id="cap-${i}">${esc(c.text)}</div>`).join("\n");
  const sets = timeline.captions.map((c, i) => {
    const start = Math.max(0, c.start);
    const end = Math.min(total, c.start + c.dur);
    return `tl.set("#cap-${i}", { opacity: 1 }, ${start.toFixed(3)});\ntl.set("#cap-${i}", { opacity: 0 }, ${end.toFixed(3)});`;
  }).join("\n");
  fs.writeFileSync(path.join(ROOT, captionFile), `<!doctype html>
<html lang="${esc(meta.language || "zh-CN")}"><head><meta charset="UTF-8"></head><body><template>
<style>
@font-face{font-family:"Noto Sans SC";src:url("./assets/fonts/NotoSansSC.woff2") format("woff2");font-weight:100 900;font-display:block}
#root{position:absolute;inset:0;pointer-events:none;font-family:"Noto Sans SC",sans-serif}
.cap{position:absolute;left:50%;bottom:48px;transform:translateX(-50%);max-width:1480px;padding:12px 26px 13px;
  background:rgba(3,8,16,.88);border:1px solid rgba(148,163,184,.22);border-radius:10px;
  color:#f8fafc;font-size:33px;line-height:1.42;text-align:center;opacity:0;letter-spacing:.01em;white-space:normal;width:max-content}
.cap::before{content:"";position:absolute;left:0;top:12px;bottom:12px;width:3px;background:#5eead4;border-radius:2px}
</style>
<div id="root" data-composition-id="captions" data-width="${width}" data-height="${height}">
${caps}
</div>
<script>
const tl = gsap.timeline({ paused: true });
${sets}
window.__timelines["captions"] = tl;
</script>
</template></body></html>`, "utf8");
  captionsHost = `  <div id="el-captions" data-composition-id="captions" data-composition-src="${captionFile}" data-start="0" data-duration="${total}" data-track-index="90" data-track-kind="captions"></div>`;
}

// ---------------------------------------------------------------- index
const hosts = sceneFiles.map((s, i) => `  <div id="el-${esc(s.id)}" data-composition-id="${esc(s.id)}" data-composition-src="compositions/${s.file}" data-start="${s.start}" data-duration="${s.duration}" data-track-index="${10 + i}"></div>`).join("\n");
const hasAudio = fs.existsSync(path.join(ROOT, "assets/mix.wav"));
if (!hasAudio) warnings.push("assets/mix.wav missing: the project is currently silent. Run scripts/mix_audio.py before the final render.");
if (timeline.estimated) warnings.push("timeline.json is estimated from text length. Run scripts/tts.py and scripts/make_timeline.py for real sync.");

const index = `<!doctype html>
<html lang="${esc(meta.language || "zh-CN")}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=${width}, height=${height}">
<title>${esc(meta.title || "CS 科普视频")}</title>
<script src="./assets/vendor/gsap.min.js"></script>
<style>
${fontFaces()}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:${width}px;height:${height}px;overflow:hidden;background:${THEME.bg}}
#root{position:relative;width:100%;height:100%;overflow:hidden;background:${THEME.bg}}
[data-composition-id="root"] > div[data-composition-src]{position:absolute;inset:0}
#progress{position:absolute;left:0;right:0;bottom:0;height:4px;background:rgba(148,163,184,.12);z-index:100}
#progress-fill{height:100%;width:100%;transform-origin:left center;background:linear-gradient(90deg,${THEME.cyan},${THEME.blue} 60%,${THEME.amber})}
</style>
</head>
<body>
<div id="root" data-composition-id="root" data-width="${width}" data-height="${height}" data-duration="${total}" data-fps="${fps}">
${hosts}
${captionsHost}
${hasAudio ? `  <audio id="mix" src="assets/mix.wav" data-start="0" data-duration="${total}" data-track-index="100" data-volume="1"></audio>` : ""}
  <div id="progress"><div id="progress-fill"></div></div>
</div>
<script>
const tl = gsap.timeline({ paused: true });
tl.fromTo("#progress-fill", { scaleX: 0 }, { scaleX: 1, duration: ${total}, ease: "none" }, 0);
window.__timelines["root"] = tl;
</script>
</body>
</html>`;

fs.writeFileSync(path.join(ROOT, "index.html"), index, "utf8");
const report = {
  title: meta.title || null,
  duration: total,
  fps,
  size: [width, height],
  estimatedTimeline: Boolean(timeline.estimated),
  audio: hasAudio ? "assets/mix.wav" : null,
  captions: timeline.captions.length,
  scenes: sceneFiles,
  warnings,
};
fs.writeFileSync(path.join(ROOT, "build-report.json"), JSON.stringify(report, null, 2));
console.log(`built ${sceneFiles.length} scenes · ${total.toFixed(2)}s · ${width}x${height}@${fps}`);
console.log(`timeline: ${timeline.estimated ? "ESTIMATED (run TTS + make_timeline.py)" : "measured"}; captions: ${timeline.captions.length}; audio: ${hasAudio ? "yes" : "NO"}`);
for (const w of warnings) console.log(`warning: ${w}`);
