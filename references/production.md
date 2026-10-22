# HyperFrames 制作

画面由 HTML/CSS/GSAP 渲染，HyperFrames 负责逐帧 seek、媒体播放和编码。这个 skill 不要求你会 React；你只需要会改 `film.json` 和少量 CSS。

## 工程怎么长出来

```sh
python3 <SKILL>/scripts/init_project.py --output <FILM>
cd <FILM>
node build.mjs
```

`init_project.py` 复制 `assets/template/`（字体、GSAP、音效、`build.mjs`、`lib/`）并写一个可改的 `film.json`。`build.mjs` 读 `film.json` + `timeline.json`，生成：

- `index.html`：HyperFrames 入口，挂载 8 个镜头、字幕轨、音频和进度条。
- `compositions/NN-<id>.html`：每镜一个 sub-composition。
- `build-report.json`：生成结果、警告、是否缺音频。

**不要手改 `index.html` / `compositions/`**。它们是生成物；下一次 `node build.mjs` 会覆盖。改 `film.json`、`lib/scenes.mjs`、`lib/theme.mjs`。

## HyperFrames 契约（最少必要）

顶层 `index.html` 的根：

```html
<div id="root" data-composition-id="root"
     data-width="1920" data-height="1080"
     data-duration="100.5" data-fps="30">
  <div data-composition-id="hook"
       data-composition-src="compositions/01-hook.html"
       data-start="0" data-duration="13.831"></div>
  <audio id="mix" src="assets/mix.wav" data-start="0" data-duration="100.5"></audio>
</div>
```

规则：

- `data-composition-id` 是时间轴注册键；宿主 div 的 id 必须等于 sub-comp 内部的 `data-composition-id`，也等于 `window.__timelines[id]`。
- 可见性由宿主 `data-start`/`data-duration` 决定；sub-comp 内部不要再用 `data-start` 包一层。
- 一个 sub-comp 只注册一个 `gsap.timeline({paused:true})`，在 `window.__timelines["<id>"]`。
- **sub-comp 内的时间是镜头本地时间**，从 0 开始。`build.mjs` 已经把 `timeline.json` 的绝对 mark 时间减去了镜头 `start`；如果你手写场景，别把绝对时间塞进 sub-comp。
- 根 `data-duration` 是总时长；最后一个镜头结束应等于它，否则末尾会黑。
- `<audio>` 必须有 `id`；不要加 `crossorigin`；音频会由 HyperFrames 混入 MP4。
- 字体必须有同文件的 `@font-face`；不要只写 `font-family:"Noto Sans SC"` 而没有字体文件。
- 不要用 `Date.now()`、`performance.now()`、未播种的 `Math.random()`、渲染时网络请求或输入状态。所有帧必须能从时间复现。

## 镜头生成

`build.mjs` 的流程：

1. 读 `film.json`（片）和 `timeline.json`（实测时间轴）；没有时间轴时按字数估一个，并打印 `ESTIMATED`。
2. 对每个 scene，调用 `lib/scenes.mjs` 的 renderer，得到 HTML + CSS。
3. 生成镜头 JS：按 mark 时间做 `fromTo`，入场元素保留在画面上做位移，揭示元素从透明进入。
4. 生成 `index.html`：宿主、字幕、音频、进度条。
5. 写 `build-report.json`。

每个镜头的页脚由 `lib/theme.mjs` 的 `sceneFooter(scene)` 生成：左侧来源、右侧备注；没有品牌、章节名或镜头编号顶栏。要改字体或颜色只改这一处。

### 镜头 JS 的关键点

```js
const tl = gsap.timeline({ paused: true });
const FIRST = false;
if (FIRST) gsap.set("[data-reveal],[data-intro]", { opacity: 1 });
animate("[data-reveal~='s0']", 0.200);      // 镜头本地时间
animate("[data-intro]", 0.06, true);         // 开场 chrome
window.__timelines["pipeline"] = tl;
```

- `FIRST` 只用于第 0 镜：首帧必须完整，所以不把元素淡出；只做位移/脉冲/下划线。
- 其他镜头的 `data-intro`（标题、卡片、终端框）在切点就可见，只做 0.55s 位移；`data-reveal` 才从透明进入。这样切点不会闪黑。
- 一个元素可以同时有 `data-reveal` 和 `data-anim`：`grow-x`、`type`、`stamp`、`wipe`、`pulse`、默认位移。
- 背景漂移用有限 `repeat`，按镜头时长截断；不要 `repeat:-1`。

### 新增镜头类型

1. 在 `lib/scenes.mjs` 写 `function myScene(ctx) { return { html, css, js } }`。
2. 在文件底部 `SCENES.myScene = myScene`。
3. 在 `references/visual-grammar.md` 补字段和规则。
4. 用 `film.json` 里一个 scene 试 build + snapshot；跑 `npx --yes hyperframes@0.8.184 check`。
5. 不要忘了 `data-reveal` 的 mark 在台词里存在；否则 build 会警告并把它放在 0.25s。

## 字体与首帧

- 模板自带 `NotoSansSC.woff2`（约 7.4MB）、`SpaceGrotesk.woff2`、`JetBrainsMono.woff2`，均为 OFL；`@font-face` 写在 `index.html` 的 `<head>`，sub-comp 继承。
- 中文字体不要依赖系统字体：渲染机可能没有 PingFang/微软雅黑。
- 首帧：第 0 镜的 `[data-reveal]` CSS 直接 `opacity:1`，JS 只做位移/脉冲；不要用 `fromTo(...,{opacity:0})`。
- 换画幅：模板的 CSS 以 1920×1080 写死；竖版需要重排字号、边距和镜头，不要直接裁。

## 字幕

`build.mjs` 生成 `compositions/captions.html`，挂载在 `data-track-index="90"`、`data-track-kind="captions"`。每条字幕是一个绝对定位的 `.cap`，JS 用 `tl.set(...,{opacity:1/0})` 控制。

- 字幕文本来自 `timeline.json` 的 `captions`，由 `make_timeline.py` 按 `，。！？；` 切分。
- 小数点不切；`0.30000000000000004` 必须完整。
- 页脚在 154px，字幕在 48px；不要改回同一行，否则会重叠。
- 字幕 `<div>` 不要设 `white-space:nowrap`，否则长句会溢出；模板用 `max-width + width:max-content`。

## 命令

```sh
cd <FILM>
node build.mjs
npx --yes hyperframes@0.8.184 lint
npx --yes hyperframes@0.8.184 check
npx --yes hyperframes@0.8.184 snapshot --at 0,8.5,19.5,35.5,48.5,65.5,78.5,88.5,98
npx --yes hyperframes@0.8.184 preview
npx --yes hyperframes@0.8.184 render --quality draft --output renders/draft.mp4
npx --yes hyperframes@0.8.184 render --quality delivery --output renders/final.mp4
```

- `check` 是最终门禁：lint + 运行时 + 布局 + 动效 + 对比度。contrast 警告也要修；深色主题的小字最容易掉到 3–4:1。
- `snapshot --at` 的每个时间点要覆盖镜头中段，不要只截开头；镜头内所有元素都出现后再看。
- 先渲 8–12 秒草稿确认动态/字幕/音频，再渲全片；全片 100 秒 1080p 在 M2 Pro 上约 90 秒。
- 渲染后必须 `ffprobe`/`check_delivery.py` 确认有音轨、时长、首帧。

## 排错

| 报错/症状 | 原因 | 改法 |
| --- | --- | --- |
| `font_family_without_font_face` | 写了字体名但没有本地 `@font-face` | 用模板字体；或把字体文件放进 `assets/fonts` 并加 `@font-face` |
| `gsap_css_transform_conflict` | CSS 初始 transform + GSAP 同属性 | 用 `fromTo`，不要在 CSS 里写初始 `translate` |
| `media_missing_id` | `<audio>` 没有 id | 加 `id="mix"` |
| `caption_track_kind_missing` | 字幕宿主没有标记 | 加 `data-track-kind="captions"` |
| `subcomposition_root_styled_by_class` | 用 root 的 class 写选择器 | 用 `#root` + 普通后代选择器 |
| `Sub-composition timelines not registered` | 宿主 id / 内部 id / timeline key 不一致 | 三处改成同一个 id |
| 画面整段空/只有标题 | mark 用了绝对时间，sub-comp 里等不到 | build 里减去 `scene.start`；检查生成的 JS |
| 切点闪黑 | 场景 gap 太大，或 intro 从 opacity 0 开始 | `sceneGap` 设 0.02；intro 保留可见只做位移 |
| 首帧空白 | 第一镜用了 opacity 0 的 reveal | 第一镜 `[data-reveal]` 初始 opacity 1，只做位移 |
| 字幕和小数被切断 | 切分把 `.` 当句号 | 用模板的 `split_caption`，不要按 `.` 切 |
| 渲染没有声音 | `<audio>` 缺失或路径错；mix 没生成 | `ls assets/mix.wav`；重建 `index.html` |
| 播放到末尾黑 | 根 `data-duration` 大于最后镜头结束 | `make_timeline.py` 重算，或改 `data-duration` |
| 字幕与页脚重叠 | `.foot` 还在 116px | 用模板的 154px，字幕 48px |

## 环境

- Node.js ≥ 22；FFmpeg/ffprobe；Chrome（HyperFrames 用系统 Chrome 或自带浏览器）。
- Python ≥ 3.9；`numpy`（音乐/混音）；`edge-tts` 可选；macOS `say` 可选。
- 不需要 React、Webpack、After Effects。渲染在本地完成；没有 API key 也能出片。
- 首次 `npx --yes hyperframes@0.8.184` 会下载 CLI；离线时先全局安装同版本。npm 缓存权限问题会让 `npx` 失败，检查 `~/.npm` 的属主。
