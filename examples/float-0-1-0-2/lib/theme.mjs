import { esc } from "./util.mjs";

// Shared visual system for every CS explainer built with this skill.
// Edit THEME once; every generated scene picks it up on the next `node build.mjs`.

export const THEME = {
  bg: "#070b14",
  bg2: "#0b1424",
  panel: "#0d1728",
  panel2: "#111d31",
  ink: "#f2f5fa",
  muted: "#a7b6c9",
  faint: "#7d8fa8",
  line: "#22334d",
  cyan: "#5eead4",
  blue: "#60a5fa",
  amber: "#fbbf24",
  coral: "#fb7185",
  green: "#34d399",
  paper: "#f4f0e6",
  paperInk: "#111820",
  paperMuted: "#586170",
};

export const FONTS = {
  display: '"Space Grotesk","Noto Sans SC",sans-serif',
  body: '"Noto Sans SC",sans-serif',
  mono: '"JetBrains Mono","Noto Sans SC",monospace',
};

export function fontFaces() {
  return `
@font-face{font-family:"Noto Sans SC";src:url("./assets/fonts/NotoSansSC.woff2") format("woff2");font-weight:100 900;font-style:normal;font-display:block}
@font-face{font-family:"Space Grotesk";src:url("./assets/fonts/SpaceGrotesk.woff2") format("woff2");font-weight:300 700;font-style:normal;font-display:block}
@font-face{font-family:"JetBrains Mono";src:url("./assets/fonts/JetBrainsMono.woff2") format("woff2");font-weight:100 800;font-style:normal;font-display:block}
`;
}

// Base CSS is injected into every sub-composition so a scene can be moved between
// films without depending on the host page. The loader scopes these styles.
export function baseCss() {
  return `
#root{
  --bg:${THEME.bg};--bg2:${THEME.bg2};--panel:${THEME.panel};--panel2:${THEME.panel2};
  --ink:${THEME.ink};--muted:${THEME.muted};--faint:${THEME.faint};--line:${THEME.line};
  --cyan:${THEME.cyan};--blue:${THEME.blue};--amber:${THEME.amber};--coral:${THEME.coral};--green:${THEME.green};
  --paper:${THEME.paper};--paper-ink:${THEME.paperInk};--paper-muted:${THEME.paperMuted};
  --display:${FONTS.display};--body:${FONTS.body};--mono:${FONTS.mono};
  position:absolute;inset:0;overflow:hidden;background:var(--bg);color:var(--ink);
  font-family:var(--body);-webkit-font-smoothing:antialiased;text-rendering:geometricPrecision;
}
#root *{box-sizing:border-box}
.scene{position:absolute;inset:0;overflow:hidden;padding:0 120px}
.grid-bg{position:absolute;inset:0;pointer-events:none;
  background-image:linear-gradient(rgba(96,165,250,.055) 1px,transparent 1px),linear-gradient(90deg,rgba(96,165,250,.055) 1px,transparent 1px);
  background-size:80px 80px;mask-image:radial-gradient(ellipse at 50% 45%,#000 25%,transparent 78%)}
.grid-bg.fine{background-size:32px 32px;opacity:.55}
.glow{position:absolute;width:1100px;height:1100px;border-radius:50%;pointer-events:none;filter:blur(10px);
  background:radial-gradient(circle,rgba(94,234,212,.10),rgba(96,165,250,.05) 42%,transparent 68%)}
.vignette{position:absolute;inset:0;pointer-events:none;background:radial-gradient(ellipse at 50% 42%,transparent 42%,rgba(0,0,0,.55) 100%)}
.scan{position:absolute;inset:0;pointer-events:none;opacity:.35;
  background:repeating-linear-gradient(0deg,rgba(255,255,255,.018) 0 1px,transparent 1px 4px)}
.topbar{position:absolute;top:52px;left:120px;right:120px;display:flex;align-items:center;justify-content:space-between;
  font-family:var(--mono);font-size:24px;letter-spacing:.08em;color:var(--muted);z-index:20}
.brand{display:flex;align-items:center;gap:16px}
.brand-mark{width:12px;height:12px;background:var(--cyan);box-shadow:0 0 18px rgba(94,234,212,.8)}
.chapter{display:flex;align-items:center;gap:12px;color:var(--faint)}
.chapter b{color:var(--ink);font-weight:500}
.chapter .dot{width:8px;height:8px;border-radius:50%;background:var(--amber)}
.foot{position:absolute;left:120px;right:120px;bottom:154px;display:flex;justify-content:space-between;align-items:flex-end;
  font-family:var(--mono);font-size:21px;line-height:1.5;color:var(--faint);z-index:20;letter-spacing:.01em}
.foot .src{max-width:1180px}
.foot b{color:var(--muted);font-weight:500}
.kicker{font-family:var(--mono);font-size:28px;letter-spacing:.14em;text-transform:uppercase;color:var(--cyan);display:flex;align-items:center;gap:16px}
.kicker::before{content:"";width:54px;height:2px;background:var(--cyan);display:block}
.h1{font-family:var(--body);font-weight:800;font-size:76px;line-height:1.16;letter-spacing:-.02em;margin:0}
.h1 em{font-style:normal;color:var(--cyan)}
.mono{font-family:var(--mono)}
.reveal{opacity:0}
.hairline{height:1px;background:var(--line)}
.chip{display:inline-flex;align-items:center;gap:10px;padding:10px 18px;border:1px solid var(--line);border-radius:999px;
  font-family:var(--mono);font-size:22px;color:var(--muted);background:rgba(13,23,40,.72)}
.chip .dot{width:8px;height:8px;border-radius:50%;background:var(--green)}
.noise{position:absolute;inset:0;pointer-events:none;opacity:.5;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='160' height='160' filter='url(%23n)' opacity='.045'/%3E%3C/svg%3E")}
`;
}

export function sceneChrome(scene, index, total) {
  const src = scene.footer ? `<div class="src">${esc(scene.footer)}</div>` : "<div></div>";
  return `
  <div class="topbar">
    <div class="brand"><span class="brand-mark"></span><span>CS / ${String(index + 1).padStart(2, "0")}</span></div>
    <div class="chapter"><span class="dot"></span><span>${esc(scene.chapter || "计算机科普")}</span><b>${String(index + 1).padStart(2, "0")} / ${String(total).padStart(2, "0")}</b></div>
  </div>
  <div class="foot">${src}<div>${esc(scene.footnote || "")}</div></div>`;
}

export function bgLayers({ fine = false, glow = true, scan = true, noise = true } = {}) {
  return `
  <div class="grid-bg${fine ? " fine" : ""}"></div>
  ${glow ? '<div class="glow" style="left:-260px;top:-420px"></div>' : ""}
  <div class="vignette"></div>
  ${scan ? '<div class="scan"></div>' : ""}
  ${noise ? '<div class="noise"></div>' : ""}`;
}
