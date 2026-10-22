import { baseCss, bgLayers, sceneFooter, THEME } from "./theme.mjs";
import { esc, groupBits } from "./util.mjs";

function shell(ctx, cls, body, opts = {}) {
  return `<div class="scene ${cls}">${bgLayers(opts)}${sceneFooter(ctx.scene)}${body}</div>`;
}

function attr(name, value) {
  return value === undefined || value === null || value === "" ? "" : `${name}="${esc(value)}"`;
}

function reveal(mark) {
  return mark ? `data-reveal="${esc(mark)}"` : "";
}

function toneClass(tone) {
  return tone ? ` tone-${esc(tone)}` : "";
}

const sharedCss = `
.stage{position:absolute;left:120px;right:120px;top:156px;bottom:150px;display:flex;flex-direction:column;justify-content:center}
.stage.top{justify-content:flex-start}
.stage-head{display:flex;flex-direction:column;gap:18px;margin-bottom:40px}
.stage-title{font-size:62px;line-height:1.16;font-weight:800;letter-spacing:-.02em;margin:0;max-width:1500px}
.stage-title em{font-style:normal;color:var(--cyan)}
.tone-cyan{color:var(--cyan)!important}.tone-blue{color:var(--blue)!important}.tone-amber{color:var(--amber)!important}
.tone-coral{color:var(--coral)!important}.tone-green{color:var(--green)!important}.tone-muted{color:var(--muted)!important}
`;

// ---------------------------------------------------------------- hook
function hook(ctx) {
  const s = ctx.scene;
  const bits = groupBits(s.bits || "0011111110111001100110011001100110011001100110011001100110011010", 8);
  const aside = bits.map((g) => `<div>${esc(g)}</div>`).join("");
  const body = `
  <div class="hook-wrap">
    <div class="hook-copy">
      <div class="kicker" data-intro>${esc(s.kicker || "一个每天都在发生的怪事")}</div>
      <div class="hook-eq" ${reveal(s.markQ || "q")} data-anim="pulse">
        <span class="hook-num">${esc(s.a || "0.1")}</span><span class="hook-op">+</span><span class="hook-num">${esc(s.b || "0.2")}</span><span class="hook-op">=</span>
      </div>
      <div class="hook-result" ${reveal(s.markResult || "result")} data-anim="pulse"><span class="hook-eqsign">=</span>${esc(s.result || "0.30000000000000004")}</div>
      <div class="hook-rule" ${reveal(s.markResult || "result")} data-anim="grow-x"></div>
      <div class="hook-note" ${reveal(s.markNote || "note")} data-anim="pulse">${esc(s.note || "这不是 bug。")}</div>
    </div>
    <aside class="hook-aside" data-float>
      <div class="hook-aside-label">BINARY64 / 0.1</div>
      <div class="hook-bits">${aside}</div>
      <div class="hook-aside-hex">${esc(s.hex || "0x3FB999999999999A")}</div>
    </aside>
  </div>`;
  return {
    html: shell(ctx, "scene-hook", body, { fine: true }),
    css: `${sharedCss}
.hook-wrap{position:absolute;inset:156px 120px 150px 120px}
.hook-copy{position:absolute;left:0;top:50%;transform:translateY(-52%);width:1330px}
.hook-eq{display:flex;align-items:baseline;gap:22px;font-family:var(--mono);font-size:132px;font-weight:700;letter-spacing:-.055em;line-height:1.05;color:var(--ink);margin:26px 0 8px}
.hook-op{color:var(--faint);font-weight:400;margin:0 4px}
.hook-rule{width:900px;height:3px;background:linear-gradient(90deg,var(--amber),rgba(251,191,36,.15));margin:18px 0 0;transform-origin:left center}
.hook-result{font-family:var(--mono);font-size:78px;font-weight:700;letter-spacing:-.04em;color:var(--amber);line-height:1.15;white-space:nowrap}
.hook-eqsign{color:var(--faint);font-weight:400;margin-right:14px}
.hook-note{font-size:38px;color:var(--ink);margin-top:28px;letter-spacing:.01em}
.hook-aside{position:absolute;right:0;top:96px;width:270px;text-align:left;border-left:1px solid var(--line);padding-left:26px}
.hook-aside-label{font-family:var(--mono);font-size:18px;letter-spacing:.16em;color:var(--faint);margin-bottom:16px}
.hook-bits{font-family:var(--mono);font-size:19px;line-height:1.9;letter-spacing:.12em;color:var(--blue);opacity:.62}
.hook-aside-hex{font-family:var(--mono);font-size:18px;color:var(--amber);opacity:.8;margin-top:18px;letter-spacing:.03em}
`,
    js: "",
  };
}

// ---------------------------------------------------------------- statement
function statement(ctx) {
  const s = ctx.scene;
  const body = `
  <div class="stmt-wrap">
    <div class="stmt-card" data-intro>
      <div class="stmt-mark">// ${esc(s.tag || "THE PIVOT")}</div>
      <div class="stmt-line" data-intro>${esc(s.line1 || "不是 bug。")}</div>
      <div class="stmt-line accent" ${reveal(s.markLine2 || "line2")}>${esc(s.line2 || "是二进制。")}</div>
      <div class="stmt-sub" ${reveal(s.markSub || "sub")}>${esc(s.sub || "")}</div>
      <div class="stmt-index">${esc(s.index || "01 — 问题的形状")}</div>
    </div>
    <div class="stmt-side" data-intro>
      <div>IEEE 754</div><div>BINARY64</div><div>53 BITS</div>
    </div>
  </div>`;
  return {
    html: shell(ctx, "scene-statement", body, { fine: false }),
    css: `${sharedCss}
.stmt-wrap{position:absolute;inset:0}
.stmt-card{position:absolute;left:120px;top:186px;width:1400px;height:612px;background:var(--paper);color:var(--paper-ink);padding:64px 82px;border-radius:8px;box-shadow:22px 22px 0 rgba(251,113,133,.92)}
.stmt-mark{font-family:var(--mono);font-size:22px;letter-spacing:.14em;color:#7c8594;margin-bottom:30px}
.stmt-line{font-size:108px;font-weight:900;line-height:1.14;letter-spacing:-.045em}
.stmt-line.accent{color:#0b6f66}
.stmt-sub{font-size:33px;line-height:1.55;color:var(--paper-muted);max-width:1030px;margin-top:34px}
.stmt-index{position:absolute;right:50px;bottom:34px;font-family:var(--mono);font-size:19px;color:#8a93a1}
.stmt-side{position:absolute;right:64px;top:250px;width:150px;font-family:var(--mono);font-size:18px;line-height:2.2;letter-spacing:.14em;color:var(--faint);text-align:right}
`,
    js: "",
  };
}

// ---------------------------------------------------------------- pipeline
function pipeline(ctx) {
  const s = ctx.scene;
  const steps = (s.steps || []).slice(0, 6);
  const cards = steps.map((step, i) => `
    <div class="pipe-step${step.tone ? " hot" : ""}" ${reveal(`s${i}`)}>
      <div class="pipe-num">${String(i + 1).padStart(2, "0")}</div>
      <div class="pipe-label${toneClass(step.tone)}${String(step.label).length > 13 ? " long" : ""}">${esc(step.label)}</div>
      <div class="pipe-sub">${esc(step.sub || "")}</div>
      ${step.note ? `<div class="pipe-note">${esc(step.note)}</div>` : ""}
    </div>${i < steps.length - 1 ? '<div class="pipe-arrow" aria-hidden="true"></div>' : ""}`).join("");
  const body = `
  <div class="stage top">
    <div class="stage-head">
      <div class="kicker" data-intro>${esc(s.kicker || "机制")}</div>
      <h2 class="stage-title" data-intro>${s.title || ""}</h2>
    </div>
    <div class="pipe-row" data-intro>${cards}</div>
    <div class="pipe-foot" ${reveal(s.markFoot || "foot")}>${esc(s.foot || "")}</div>
  </div>`;
  return {
    html: shell(ctx, "scene-pipeline", body, { fine: true }),
    css: `${sharedCss}
.pipe-row{display:flex;align-items:stretch;width:100%;min-height:340px}
.pipe-step{flex:1 1 0;min-width:0;min-height:340px;background:linear-gradient(180deg,rgba(17,29,49,.96),rgba(11,20,36,.96));border:1px solid var(--line);border-radius:10px;padding:24px 20px 22px;display:flex;flex-direction:column;gap:12px}
.pipe-step.hot{border-color:rgba(251,191,36,.65);background:linear-gradient(180deg,rgba(251,191,36,.12),rgba(11,20,36,.96))}
.pipe-num{font-family:var(--mono);font-size:19px;color:var(--faint);letter-spacing:.1em}
.pipe-label{font-family:var(--mono);font-size:27px;font-weight:700;line-height:1.28;overflow-wrap:anywhere;letter-spacing:-.03em}
.pipe-label.long{font-size:21px;line-height:1.45}
.pipe-sub{font-size:21px;line-height:1.45;color:var(--muted)}
.pipe-note{margin-top:auto;font-family:var(--mono);font-size:18px;color:var(--faint);line-height:1.4}
.pipe-arrow{flex:0 0 42px;align-self:center;height:2px;background:var(--line);position:relative;transform-origin:left center}
.pipe-arrow::after{content:"";position:absolute;right:0;top:-5px;width:10px;height:10px;border-top:2px solid var(--line);border-right:2px solid var(--line);transform:rotate(45deg)}
.pipe-foot{margin-top:36px;font-size:33px;line-height:1.5;color:var(--ink);letter-spacing:.01em}
.pipe-foot::before{content:"";display:inline-block;width:10px;height:10px;background:var(--amber);margin-right:16px;vertical-align:middle}
`,
    js: "",
  };
}

// ---------------------------------------------------------------- bitfield
function bitfield(ctx) {
  const s = ctx.scene;
  const segments = s.segments || [
    { label: "符号", bits: 1, tone: "amber", note: "0 正 / 1 负" },
    { label: "指数", bits: 11, tone: "cyan", note: "偏置 1023" },
    { label: "尾数", bits: 52, tone: "blue", note: "隐含最高位 1" },
  ];
  const totalBits = segments.reduce((n, x) => n + Number(x.bits), 0) || 64;
  const bars = segments.map((seg, i) => {
    const pct = (Number(seg.bits) / totalBits) * 100;
    return `<div class="bf-seg${toneClass(seg.tone)}${seg.tone ? " bg-" + esc(seg.tone) : ""}" style="width:${pct.toFixed(3)}%" ${reveal(`b${i}`)} data-anim="grow-x">
      <span class="bf-count">${esc(seg.bits)}</span>${Number(seg.bits) > 8 ? `<span class="bf-name">${esc(seg.label)}</span>` : ""}
    </div>`;
  }).join("");
  const legend = segments.map((seg) => `<div class="bf-leg"><i class="bg-${esc(seg.tone || "blue")}"></i><b>${esc(seg.label)}</b><span>${esc(seg.bits)} 位</span><em>${esc(seg.note || "")}</em></div>`).join("");
  const rawBits = String(s.bits || "0011111110111001100110011001100110011001100110011001100110011010").replace(/\s+/g, "");
  const bitSpans = [...rawBits].map((bit, i) => {
    const cls = i === 0 ? "bg-amber" : i < 12 ? "bg-cyan" : "bg-blue";
    const gap = i > 0 && i % 4 === 0 ? " bit-gap" : "";
    return `<span class="bf-bit ${cls}${gap}">${bit}</span>`;
  }).join("");
  const body = `
  <div class="stage top">
    <div class="stage-head">
      <div class="kicker" data-intro>${esc(s.kicker || "编码")}</div>
      <h2 class="stage-title" data-intro>${s.title || ""}</h2>
    </div>
    <div class="bf-bar" data-intro>${bars}</div>
    <div class="bf-legend" data-intro>${legend}</div>
    <div class="bf-readout" ${reveal(s.markBits || "bits")}>
      <div class="bf-readout-head"><span>0.1 的 binary64 位模式</span><b>${esc(s.hex || "0x3FB999999999999A")}</b></div>
      <div class="bf-bitline">${bitSpans}</div>
      <div class="bf-note">${esc(s.note || "52 位尾数 + 1 位隐含的 1 = 53 位有效数字。")}</div>
    </div>
  </div>`;
  return {
    html: shell(ctx, "scene-bitfield", body, { fine: true }),
    css: `${sharedCss}
.bf-bar{display:flex;gap:6px;height:152px;width:100%;margin-top:8px}
.bf-seg{height:100%;border-radius:6px;position:relative;display:flex;align-items:center;justify-content:center;gap:14px;overflow:hidden;transform-origin:left center;border:1px solid rgba(255,255,255,.12)}
.bf-seg.bg-amber{background:linear-gradient(180deg,rgba(251,191,36,.88),rgba(180,120,10,.72))}
.bf-seg.bg-cyan{background:linear-gradient(180deg,rgba(94,234,212,.78),rgba(20,130,120,.55))}
.bf-seg.bg-blue{background:linear-gradient(180deg,rgba(96,165,250,.75),rgba(30,80,170,.55))}
.bf-count{font-family:var(--mono);font-size:56px;font-weight:700;color:#f8fafc;letter-spacing:-.04em}
.bf-name{font-size:24px;font-weight:700;color:rgba(248,250,252,.88)}
.bf-seg:first-child{border-radius:6px 2px 2px 6px}
.bf-seg:first-child .bf-count{font-size:24px;color:#2a1a00}
.bf-legend{display:flex;gap:40px;margin-top:24px;align-items:baseline}
.bf-leg{display:flex;align-items:baseline;gap:10px;font-size:20px;color:var(--muted);white-space:nowrap}
.bf-leg i{width:12px;height:12px;border-radius:3px;flex:0 0 12px}
.bf-leg i.bg-amber{background:var(--amber)}.bf-leg i.bg-cyan{background:var(--cyan)}.bf-leg i.bg-blue{background:var(--blue)}
.bf-leg b{color:var(--ink);font-weight:700}
.bf-leg span{font-family:var(--mono);font-size:18px;color:var(--faint)}
.bf-leg em{font-style:normal;font-size:18px;color:var(--faint);margin-left:2px}
.bf-readout{margin-top:44px;border-top:1px solid var(--line);padding-top:26px}
.bf-readout-head{display:flex;justify-content:space-between;align-items:baseline;font-family:var(--mono);font-size:20px;color:var(--muted);letter-spacing:.06em}
.bf-readout-head b{color:var(--amber);font-weight:500}
.bf-bitline{margin-top:18px;font-family:var(--mono);font-size:25px;line-height:1.4;white-space:nowrap;letter-spacing:.06em}
.bf-bit{opacity:.92}
.bf-bit.bg-amber{color:var(--amber)}.bf-bit.bg-cyan{color:var(--cyan)}.bf-bit.bg-blue{color:var(--blue)}
.bf-bit.bit-gap{margin-left:12px}
.bf-note{margin-top:20px;font-size:25px;color:var(--ink)}
`,
    js: "",
  };
}

export const SCENES = { hook, statement, pipeline, bitfield };

// ---------------------------------------------------------------- code
function code(ctx) {
  const s = ctx.scene;
  const lines = (s.lines || []).map((line) => (typeof line === "string" ? { text: line, tone: "in" } : line));
  const rendered = lines.map((line, i) => {
    const tone = line.tone || "in";
    const text = esc(line.text);
    const prompt = tone === "in" && /^>>> ?/.test(line.text) ? '<span class="code-prompt">&gt;&gt;&gt; </span>' : "";
    const body = prompt ? text.replace(/^&gt;&gt;&gt; ?/, "") : text;
    return `<div class="code-line tone-${esc(tone)}" ${reveal(line.mark || (s.autoMarks === false ? "" : `l${i}`))} data-anim="type"><span class="code-gutter">${String(i + 1).padStart(2, "0")}</span><span class="code-text">${prompt}${body}</span></div>`;
  }).join("");
  const body = `
  <div class="code-wrap">
    <div class="code-card" data-intro>
      <div class="code-bar"><span class="code-dot r"></span><span class="code-dot y"></span><span class="code-dot g"></span><span class="code-lang">${esc(s.lang || "python3")}</span></div>
      <div class="code-body">${rendered}</div>
    </div>
    <div class="code-side">
      <div class="kicker" data-intro>${esc(s.kicker || "验证")}</div>
      <h2 class="code-title" data-intro>${(s.titleLines || [s.title || ""]).map((line) => `<span>${esc(line)}</span>`).join("")}</h2>
      <div class="code-note" ${reveal(s.markNote || "note")}>${esc(s.note || "")}</div>
      ${s.aside ? `<div class="code-aside" data-intro>${esc(s.aside)}</div>` : ""}
    </div>
  </div>`;
  return {
    html: shell(ctx, "scene-code", body, { fine: true }),
    css: `${sharedCss}
.code-wrap{position:absolute;inset:158px 120px 150px;display:flex;gap:44px;align-items:center}
.code-card{flex:1 1 auto;min-width:0;background:#040910;border:1px solid var(--line);border-radius:12px;overflow:hidden;box-shadow:0 30px 80px rgba(0,0,0,.45)}
.code-bar{height:54px;display:flex;align-items:center;gap:9px;padding:0 22px;background:#0a1322;border-bottom:1px solid var(--line)}
.code-dot{width:11px;height:11px;border-radius:50%}
.code-dot.r{background:#fb7185}.code-dot.y{background:#fbbf24}.code-dot.g{background:#34d399}
.code-lang{margin-left:12px;font-family:var(--mono);font-size:18px;color:var(--faint);letter-spacing:.08em}
.code-body{padding:24px 26px 26px}
.code-line{display:flex;gap:18px;font-family:var(--mono);font-size:27px;line-height:1.62;white-space:pre;color:var(--ink)}
.code-gutter{color:#334155;font-size:17px;width:28px;flex:0 0 28px;line-height:2.5}
.code-text{min-width:0}
.code-line.tone-out .code-text{color:var(--amber)}
.code-line.tone-str .code-text{color:var(--green)}
.code-line.tone-err .code-text{color:var(--coral)}
.code-line.tone-comment .code-text{color:var(--faint)}
.code-line.tone-dim .code-text{color:var(--muted)}
.code-prompt{color:var(--cyan)}
.code-side{flex:0 0 440px;display:flex;flex-direction:column;gap:22px}
.code-title{font-size:46px;line-height:1.22;font-weight:800;letter-spacing:-.02em;margin:0;text-wrap:balance}
.code-title span{display:block}
.code-note{font-size:27px;line-height:1.55;color:var(--muted)}
.code-aside{margin-top:auto;font-family:var(--mono);font-size:18px;line-height:1.6;color:var(--faint);border-top:1px solid var(--line);padding-top:18px;word-break:break-all}
`,
    js: "",
  };
}

// ---------------------------------------------------------------- compare
function compare(ctx) {
  const s = ctx.scene;
  const card = (side, data, cls) => `
    <div class="cmp-card ${cls}" ${reveal(side)}>
      <div class="cmp-tag">${esc(data.tag || "")}</div>
      <div class="cmp-title">${esc(data.title || "")}</div>
      <div class="cmp-value">${esc(data.value || "")}</div>
      <div class="cmp-note">${esc(data.note || "")}</div>
    </div>`;
  const body = `
  <div class="stage top">
    <div class="stage-head"><div class="kicker" data-intro>${esc(s.kicker || "对照")}</div><h2 class="stage-title" data-intro>${s.title || ""}</h2></div>
    <div class="cmp-row">
      ${card("left", s.left || {}, "paper")}
      <div class="cmp-vs" data-intro>VS</div>
      ${card("right", s.right || {}, "dark")}
    </div>
    <div class="cmp-verdict" ${reveal(s.markVerdict || "verdict")}>${esc(s.verdict || "")}</div>
  </div>`;
  return {
    html: shell(ctx, "scene-compare", body, { fine: true }),
    css: `${sharedCss}
.cmp-row{display:flex;align-items:stretch;gap:0;margin-top:8px}
.cmp-card{flex:1 1 0;min-width:0;height:450px;padding:38px 42px;border-radius:10px;display:flex;flex-direction:column}
.cmp-card.paper{background:var(--paper);color:var(--paper-ink);box-shadow:16px 16px 0 rgba(251,113,133,.9)}
.cmp-card.dark{background:linear-gradient(180deg,rgba(17,29,49,.98),rgba(8,14,26,.98));border:1px solid rgba(94,234,212,.45);margin-left:80px}
.cmp-tag{font-family:var(--mono);font-size:19px;letter-spacing:.16em;color:#7c8594;margin-bottom:20px}
.cmp-card.dark .cmp-tag{color:var(--cyan)}
.cmp-title{font-size:38px;font-weight:800;line-height:1.3}
.cmp-value{font-family:var(--mono);font-size:44px;line-height:1.35;margin-top:26px;word-break:break-all}
.cmp-card.paper .cmp-value{color:#8a3b12}
.cmp-card.dark .cmp-value{color:var(--amber);font-size:30px}
.cmp-note{margin-top:auto;font-size:23px;line-height:1.55;color:var(--paper-muted)}
.cmp-card.dark .cmp-note{color:var(--muted)}
.cmp-vs{flex:0 0 90px;align-self:center;width:86px;height:86px;border-radius:50%;display:grid;place-items:center;font-family:var(--mono);font-size:22px;color:var(--ink);background:var(--bg2);border:1px solid var(--line);margin-left:-6px;z-index:2}
.cmp-verdict{margin-top:40px;font-size:36px;color:var(--ink)}
.cmp-verdict::before{content:"";display:inline-block;width:10px;height:10px;background:var(--amber);margin-right:16px;vertical-align:middle}
`,
    js: "",
  };
}

// ---------------------------------------------------------------- numbers
function numbers(ctx) {
  const s = ctx.scene;
  const stats = (s.stats || []).slice(0, 4);
  const cards = stats.map((stat, i) => `
    <div class="num-card${stat.tone ? " hot" : ""}" ${reveal(`n${i}`)}>
      <div class="num-idx">${String(i + 1).padStart(2, "0")}</div>
      <div class="num-value${toneClass(stat.tone)}">${esc(stat.value)}<span class="num-unit">${esc(stat.unit || "")}</span></div>
      <div class="num-label">${esc(stat.label || "")}</div>
      <div class="num-note">${esc(stat.note || "")}</div>
    </div>`).join("");
  const body = `
  <div class="stage top">
    <div class="stage-head"><div class="kicker" data-intro>${esc(s.kicker || "尺度")}</div><h2 class="stage-title" data-intro>${s.title || ""}</h2></div>
    <div class="num-row" data-intro>${cards}</div>
    ${s.equation ? `<div class="num-eq" ${reveal(s.markEq || "eq")}>${esc(s.equation)}</div>` : ""}
  </div>`;
  return {
    html: shell(ctx, "scene-numbers", body, { fine: false }),
    css: `${sharedCss}
.num-row{display:flex;gap:32px;margin-top:6px}
.num-card{flex:1 1 0;min-width:0;min-height:380px;background:linear-gradient(180deg,rgba(17,29,49,.96),rgba(9,16,29,.96));border:1px solid var(--line);border-radius:12px;padding:30px 32px;display:flex;flex-direction:column}
.num-card.hot{border-color:rgba(251,191,36,.55);background:linear-gradient(180deg,rgba(251,191,36,.13),rgba(9,16,29,.96))}
.num-idx{font-family:var(--mono);font-size:18px;color:var(--muted);letter-spacing:.12em}
.num-value{font-family:var(--display);font-size:104px;font-weight:700;line-height:1.1;letter-spacing:-.05em;margin-top:16px;color:var(--cyan)}
.num-unit{font-family:var(--body);font-size:30px;font-weight:500;color:var(--muted);margin-left:10px;letter-spacing:0}
.num-label{font-size:27px;font-weight:700;line-height:1.4;margin-top:14px}
.num-note{font-size:20px;line-height:1.55;color:var(--faint);margin-top:auto;padding-top:18px}
.num-eq{margin-top:42px;font-family:var(--mono);font-size:27px;line-height:1.5;color:var(--muted);border-left:2px solid var(--amber);padding-left:22px}
`,
    js: "",
  };
}

// ---------------------------------------------------------------- layers
function layers(ctx) {
  const s = ctx.scene;
  const rows = (s.layers || []).map((layer, i) => `
    <div class="lay-row" ${reveal(`y${i}`)}>
      <div class="lay-label">${esc(layer.label)}${layer.sub ? `<span>${esc(layer.sub)}</span>` : ""}</div>
      <div class="lay-track"><div class="lay-fill${toneClass(layer.tone)}" ${reveal(`y${i}`)} data-anim="grow-x" style="width:${Math.max(4, Math.min(100, Number(layer.pct ?? 100)))}%"></div></div>
      <div class="lay-note">${esc(layer.note || "")}</div>
    </div>`).join("");
  const body = `
  <div class="stage top">
    <div class="stage-head"><div class="kicker" data-intro>${esc(s.kicker || "层次")}</div><h2 class="stage-title" data-intro>${s.title || ""}</h2></div>
    <div class="lay-list" data-intro>${rows}</div>
    ${s.foot ? `<div class="lay-foot" ${reveal(s.markFoot || "foot")}>${esc(s.foot)}</div>` : ""}
  </div>`;
  return {
    html: shell(ctx, "scene-layers", body, { fine: true }),
    css: `${sharedCss}
.lay-list{display:flex;flex-direction:column;gap:18px;margin-top:8px}
.lay-row{display:grid;grid-template-columns:230px 1fr 300px;gap:26px;align-items:center;min-height:96px;background:rgba(13,23,40,.55);border:1px solid var(--line);border-radius:8px;padding:18px 24px}
.lay-label{font-size:26px;font-weight:700;line-height:1.3}
.lay-label span{display:block;font-family:var(--mono);font-size:17px;color:var(--faint);font-weight:400;margin-top:4px}
.lay-track{height:40px;background:#060b14;border-radius:4px;overflow:hidden;border:1px solid rgba(255,255,255,.05)}
.lay-fill{height:100%;background:var(--blue);transform-origin:left center;border-radius:3px}
.lay-fill.tone-cyan{background:var(--cyan)}.lay-fill.tone-amber{background:var(--amber)}.lay-fill.tone-green{background:var(--green)}.lay-fill.tone-coral{background:var(--coral)}
.lay-note{font-size:20px;line-height:1.5;color:var(--muted);text-align:right}
.lay-foot{margin-top:34px;font-size:30px;color:var(--ink)}
`,
    js: "",
  };
}

// ---------------------------------------------------------------- recap
function recap(ctx) {
  const s = ctx.scene;
  const items = (s.items || []).map((item, i) => `
    <div class="rec-row" ${reveal(`r${i}`)}>
      <div class="rec-num">${esc(item.n || String(i + 1).padStart(2, "0"))}</div>
      <div class="rec-main">
        <div class="rec-title">${esc(item.title)}</div>
        <div class="rec-note">${esc(item.note || "")}</div>
      </div>
      ${item.code ? `<div class="rec-code">${esc(item.code)}</div>` : ""}
    </div>`).join("");
  const body = `
  <div class="stage top">
    <div class="stage-head"><div class="kicker" data-intro>${esc(s.kicker || "小结")}</div><h2 class="stage-title" data-intro>${s.title || ""}</h2></div>
    <div class="rec-list" data-intro>${items}</div>
    ${s.foot ? `<div class="rec-foot" ${reveal(s.markFoot || "foot")}>${esc(s.foot)}</div>` : ""}
  </div>`;
  return {
    html: shell(ctx, "scene-recap", body, { fine: true }),
    css: `${sharedCss}
.rec-list{display:flex;flex-direction:column;gap:16px;margin-top:4px}
.rec-row{display:grid;grid-template-columns:86px 1fr auto;gap:28px;align-items:center;min-height:150px;border-top:1px solid var(--line);padding:18px 6px}
.rec-row:last-child{border-bottom:1px solid var(--line)}
.rec-num{font-family:var(--mono);font-size:26px;color:var(--cyan);letter-spacing:.06em}
.rec-title{font-size:40px;font-weight:800;line-height:1.32;letter-spacing:-.01em}
.rec-note{font-size:23px;line-height:1.55;color:var(--muted);margin-top:8px}
.rec-code{font-family:var(--mono);font-size:21px;color:var(--amber);background:rgba(251,191,36,.08);border:1px solid rgba(251,191,36,.24);padding:14px 18px;border-radius:6px;max-width:520px;line-height:1.5}
.rec-foot{margin-top:30px;font-size:29px;color:var(--ink)}
.rec-foot::before{content:"";display:inline-block;width:9px;height:9px;background:var(--green);margin-right:14px;vertical-align:middle}
`,
    js: "",
  };
}

// ---------------------------------------------------------------- outro
function outro(ctx) {
  const s = ctx.scene;
  const lines = (s.questionLines || String(s.question || "").split("|")).filter(Boolean);
  const rendered = lines.map((line, i) => `<div class="outro-line" ${reveal(`q${i}`)} data-anim="wipe">${esc(line)}</div>`).join("");
  const sources = (s.sources || []).map((x) => `<span>${esc(x)}</span>`).join("");
  const body = `
  <div class="outro-wrap">
    <div class="outro-main">
      <div class="kicker" data-intro>${esc(s.kicker || "留一个问题")}</div>
      <div class="outro-question" data-intro>${rendered}</div>
      ${s.next ? `<div class="outro-next" ${reveal(s.markNext || "next")}><span class="chip"><span class="dot"></span>${esc(s.next)}</span></div>` : ""}
    </div>
    <div class="outro-side" data-intro>
      <div class="outro-hex">${esc(s.teaser || "float.hex(0.1)")}</div>
      <div class="outro-hexval">${esc(s.teaserValue || "0x1.999999999999ap-4")}</div>
    </div>
    <div class="outro-src" data-intro>${sources}</div>
  </div>`;
  return {
    html: shell(ctx, "scene-outro", body, { fine: true }),
    css: `${sharedCss}
.outro-wrap{position:absolute;inset:156px 120px 150px;display:flex;align-items:center}
.outro-main{width:1320px}
.outro-question{margin-top:28px;font-size:92px;font-weight:900;line-height:1.16;letter-spacing:-.04em}
.outro-line{white-space:nowrap}
.outro-line:nth-child(2){color:var(--cyan)}
.outro-next{margin-top:40px}
.outro-next .chip{font-family:var(--body);font-size:25px;padding:14px 22px}
.outro-side{position:absolute;right:0;bottom:110px;width:390px;text-align:right;font-family:var(--mono)}
.outro-hex{font-size:19px;color:var(--faint);letter-spacing:.06em}
.outro-hexval{font-size:24px;color:var(--amber);margin-top:10px}
.outro-src{position:absolute;left:0;bottom:36px;display:flex;gap:34px;font-family:var(--mono);font-size:19px;color:var(--faint)}
.outro-src span::before{content:"·";margin-right:12px;color:var(--cyan)}
`,
    js: "",
  };
}

SCENES.code = code;
SCENES.compare = compare;
SCENES.numbers = numbers;
SCENES.layers = layers;
SCENES.recap = recap;
SCENES.outro = outro;
