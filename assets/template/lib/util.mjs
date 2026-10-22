export function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function pad2(n) {
  return String(n).padStart(2, "0");
}

export function slug(value) {
  return String(value || "scene")
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40) || "scene";
}

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

// Readable caption chunks: split Chinese/Latin sentences at natural punctuation,
// then merge tiny fragments so a caption never flashes for a single character.
export function splitCaption(text, maxLen = 26) {
  const clean = String(text ?? "").replace(/\s+/g, " ").trim();
  if (!clean) return [];
  const parts = clean.match(/[^，。！？；：、!?;]+[，。！？；：、!?;]?/g) || [clean];
  const merged = [];
  for (const part of parts) {
    const piece = part.trim();
    if (!piece) continue;
    if (merged.length && (merged.at(-1) + piece).length <= maxLen) merged[merged.length - 1] += piece;
    else merged.push(piece);
  }
  const out = [];
  for (const piece of merged) {
    if (piece.length <= maxLen + 6) {
      out.push(piece);
      continue;
    }
    for (let i = 0; i < piece.length; i += maxLen) out.push(piece.slice(i, i + maxLen));
  }
  return out;
}

export function cpsFor(lang = "zh") {
  return lang.startsWith("zh") ? 4.4 : 14;
}

// Fallback timeline used before narration exists. Every later stage replaces it
// with measured speech durations; the build never invents a different story.
export function estimateTimeline(film) {
  const cps = cpsFor(film.meta?.language || "zh");
  const scenes = [];
  let cursor = 0;
  const captions = [];
  film.scenes.forEach((scene, index) => {
    const gap = index === 0 ? 0 : Number(scene.gap ?? film.meta?.sceneGap ?? 0.02);
    const start = cursor + gap;
    const marks = {};
    const chunks = [];
    let local = Number(scene.lead ?? 0.15);
    (scene.narration || []).forEach((line) => {
      const text = line.tts || line.caption || "";
      const dur = Math.max(1.1, text.replace(/\s/g, "").length / cps + Number(line.pause ?? 0.25));
      if (line.mark && !(line.mark in marks)) marks[line.mark] = Number((start + local + 0.04).toFixed(3));
      chunks.push({ caption: line.caption || text, text, start: Number((start + local).toFixed(3)), dur: Number(dur.toFixed(3)), mark: line.mark || null, sfx: line.sfx || null });
      for (const piece of splitCaption(line.caption || text)) {
        const pDur = Math.max(0.9, dur * (piece.length / Math.max(1, (line.caption || text).length)));
        captions.push({ text: piece, start: Number((start + local).toFixed(3)), dur: Number(pDur.toFixed(3)) });
      }
      local += dur;
    });
    const tail = Number(scene.tail ?? film.meta?.sceneTail ?? 0.7);
    const duration = Math.max(Number(scene.minDuration ?? 2.4), local + tail);
    scenes.push({ id: scene.id, index, start: Number(start.toFixed(3)), duration: Number(duration.toFixed(3)), marks, chunks, estimated: true });
    cursor = start + duration;
  });
  const total = Number(cursor.toFixed(3));
  return { version: 1, estimated: true, duration: total, scenes, captions: capCaptions(captions, total) };
}

export function capCaptions(captions, total) {
  const sorted = captions
    .map((c) => ({ ...c }))
    .sort((a, b) => a.start - b.start);
  for (let i = 0; i < sorted.length; i++) {
    const c = sorted[i];
    c.start = Math.max(0, c.start);
    const next = sorted[i + 1];
    c.dur = Math.max(0.5, Math.min(c.dur, (next ? next.start : total) - c.start - 0.06));
    if (c.start + c.dur > total) c.dur = Math.max(0.4, total - c.start - 0.05);
  }
  return sorted;
}

export function sceneTimeline(timeline, sceneId, index) {
  return timeline.scenes.find((s) => s.id === sceneId) || timeline.scenes[index];
}

export function fmtTime(value) {
  return Number(value).toFixed(3).replace(/\.?0+$/, "") || "0";
}

export function groupBits(bits, group = 4) {
  const raw = String(bits || "").replace(/\s+/g, "");
  return raw.match(new RegExp(`.{1,${group}}`, "g")) || [];
}
