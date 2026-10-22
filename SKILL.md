---
name: pop-science-video
description: 把一个概念做成一个科普视频：先核对事实与理解路径，再用代码生成的图示、真实代码输出、中文旁白、原创配乐与音效，渲染成 MP4。
---

# 科普视频 skill

把概念讲明白：观众看完能复述一个机制，而不是记住一串名词。画面、旁白和声音一起推进；每个视觉手法都要能说出“因为概念有 X，所以画面用 Y”。

本文术语：**工程**指视频工程目录；**片**指 `film.json`；**时间轴**指 `timeline.json`；**台账**指 `facts.json`；**样片**指未完成配音/混音的技术预览。

## 流程

1. **锁定 brief。** 新片先确认：讲哪个概念、给谁看（好奇的大众／会写代码的人／学生）、多长、发在哪、语言、视觉倾向。缺项一次问清，最多三个问题；默认 16:9、1920×1080、30fps、90 秒、中文、“实验室”风格。用户说“先看方向”时，只做到第 3 步。已有工程沿用已有决定，只改本次要求。
2. **做事实台账。** 找 2–4 个高可信来源；把每条要在片中说出的事实写进 `facts.json`，标状态、来源、核验方式和适用边界；代码输出必须实机跑过；常见误解和类比的“断裂点”单独列出。写成 `SOURCES.md`，再跑 `check_content.py`。**没有台账，不进入写片。**
3. **定叙事方向。** 先写一句话主张和“观众现在以为 → 卡在哪 → 先给什么 → 用什么类比 → 类比在哪失效”。提出三个差异明显的角度，选一个并写理由；列出 3–5 个从概念推导的专属手法；把字号、颜色语义、动效节奏和镜头表写进 `DIRECTION.md`。正式片必须有这份文件。用户想先看方案时，给三个角度 + 3–6 张关键画面描述，等反馈再继续。
4. **写片与台词。** 按 [叙事结构](references/story-structure.md) 和 [台词与配音](references/script-and-voice.md) 写 `film.json`：每镜一个主张，旁白按“句”切分，句子上标 `mark` 把画面揭示钉在语音上。同步写 `SCRIPT.md`。跑 `check_content.py`，把“字数 / 秒”拉回 3.5–5.5 的区间。
5. **初始化并检查环境。** 用 `init_project.py` 建独立工程；`check_environment.py` 只报告缺项，按提示补装后复查。已有工程跳过初始化，先跑环境检查。**不要在 skill 目录里直接做片。**
6. **配音、时间轴与声音。** 正式片优先真人：`make_recording_kit.py` 导出逐句录音稿，录完用 `import_recordings.py` 导入；`tts.py` 只做草稿或没有录音条件时的方案。两者都落到 `assets/tts/manifest.json`。先试听前 3 句，确认术语读音和语气，再跑全片；`make_timeline.py` 用真实时长排镜头、字幕和 mark；`music.py` 按镜头边界写原创配乐；`mix_audio.py` 做旁白让位、混音和 −16 LUFS 标准化。用了 TTS 就在交付里注明 provider/voice，不能伪装真人。
7. **搭建、检查、渲染。** `node build.mjs` 生成 HyperFrames 工程；`npx --yes hyperframes@0.8.184 check` 必须通过；按镜头中点 `snapshot` 逐张看全尺寸帧，修完再渲染。正式片用 `--quality delivery`，先渲 8–12 秒草稿确认动态，再渲全片。
8. **审片与交付。** 按 [审片与交付](references/review-and-delivery.md) 做事实、理解、画面、声音四遍审阅；`check_delivery.py` 只证明文件、时长、响度和首帧，不替代观看与试听。交付 MP4、可复现工程、关键静帧、`SOURCES.md` / `facts.json` / 两份检查报告，并说清哪些已验证、哪些仍有条件限制。

## 硬约束

- **事实可追溯。** 正式片至少两条 primary source；每条主张有 `facts.json` 记录；代码输出实机运行；数字给单位、口径和时间。范围只覆盖你核过的那部分，不把“我查到的”说成“全部”。
- **先解释，再炫技。** 每镜只推进一个主张；术语第一次出现时给中文解释或一句人话；不堆历史、不铺陈无关版本。
- **类比必须标边界。** 写清它对应机制的哪一部分、在哪一步失效。不能用类比替代机制。
- **画面为理解服务。** 1080p 下正文 ≥ 24px；一屏 ≤ 7 个节点；坐标轴/单位/数量级不能省；示意图不按比例时明确写“示意”；不伪造终端输出、数据或界面。**不放常驻顶栏**：品牌、章节名、镜头编号、页码都不进画面；页脚只保留来源、口径、边界这类观众用得上的信息。
- **首帧就是完整画面。** 第 1 帧要能当缩略图：完整标题/表达式/结果，不能是空白底或等待入场。开场动画从完整画面开始做微动，或把揭示放在第 0.5 秒之后。
- **声音完整。** 正式片优先真人旁白；旁白 + 配乐 + 动作音效；说话时音乐让位；成片 −16 LUFS 左右，真峰值 ≤ −1.5 dBFS；字幕与语音同步。用了 TTS 必须在交付说明里写清。
- **可复现。** 字体、GSAP、音频、图片全部本地化；渲染时不依赖网络、时钟、随机数或输入状态。时间只从 `timeline.json` 读。
- **隔离与授权。** 视频工程独立；素材记录来源和许可；不把产品代码、第三方素材或字体重新授权。

## 默认值

| 项 | 默认 |
| --- | --- |
| 画幅 / 帧率 | 1920×1080 / 30fps（竖版需重排，不直接裁） |
| 时长 | 90 秒（60 秒短版 / 3–6 分钟深讲另排结构） |
| 语言 | 中文；英文术语首次出现时给中文解释 |
| 受众 | 对计算机好奇、但没有相关背景 |
| 视觉 | 深蓝黑底、青色“正确路径”、琥珀“结果/注意”、珊瑚“错误”；Noto Sans SC + JetBrains Mono |
| 旁白 | 真人优先；中文 3.5–5.5 字/秒；一句一个意思 |
| 声音 | 原创配乐 + 8 个内置音效；−16 LUFS |
| 交付 | MP4 + 工程 + 静帧 + 来源/事实 + 检查报告 |

常用起点：横版、90 秒、中文、好奇的大众。用户给了平台/时长/语言就覆盖默认值。

## 工程结构

```text
<film>/
  film.json              # 片：meta + scenes + narration + 视觉数据
  timeline.json          # 实测时间轴：scene start/duration、marks、captions
  SCRIPT.md              # 台词、屏幕字、读音备注
  DIRECTION.md           # 一句话、理解路径、三个角度、专属手法、镜头表
  SOURCES.md             # 人读的来源表
  facts.json             # 机器可读的 claim / source / analogy 台账
  build.mjs              # film.json + timeline.json → HyperFrames HTML
  lib/                   # theme / scenes / util
  recording/             # 真人：NARRATION.md / lines.csv / takes/
  assets/
    fonts/               # Noto Sans SC / Space Grotesk / JetBrains Mono（OFL）
    vendor/gsap.min.js   # 本地 GSAP
    sfx/                 # 原创 WAV
    tts/                 # 逐句旁白 + manifest.json
    music.wav            # 原创配乐
    mix.wav              # 旁白 + 音乐 + 音效
  compositions/          # 生成：每镜一个 sub-composition
  index.html             # 生成：HyperFrames 入口
  evidence/              # 核验输出、timing / music / audio-mix / 检查报告
  renders/               # final.mp4、草稿
  stills/                # 关键帧、联系表
```

## 工具入口

`<SKILL>` 是 skill 根目录，`<FILM>` 是工程目录（必须在 skill 目录之外）。

```sh
# 0. 新工程（已有工程跳过）
python3 <SKILL>/scripts/init_project.py --output <FILM>
python3 <SKILL>/scripts/check_environment.py --project <FILM>

# 1. 内容与时间轴
python3 <SKILL>/scripts/check_content.py --project <FILM>
python3 <SKILL>/scripts/make_recording_kit.py --project <FILM>   # 真人：导出逐句录音稿
python3 <SKILL>/scripts/import_recordings.py --project <FILM>    # 真人：导入 takes，重建 manifest
python3 <SKILL>/scripts/audition_voices.py --project <FILM>      # 可选：本机音色试听
python3 <SKILL>/scripts/tts.py --project <FILM>                  # 草稿：edge / say / file / auto
python3 <SKILL>/scripts/make_timeline.py --project <FILM>
python3 <SKILL>/scripts/music.py --project <FILM> --mood curious
python3 <SKILL>/scripts/mix_audio.py --project <FILM>
# 暂时只去掉机器音（音乐+字幕，非正式片）：python3 <SKILL>/scripts/mix_audio.py --project <FILM> --mute-voice

# 2. 搭建与渲染
cd <FILM> && node build.mjs
npx --yes hyperframes@0.8.184 check
npx --yes hyperframes@0.8.184 snapshot --at <镜头中点逗号分隔>
npx --yes hyperframes@0.8.184 preview
npx --yes hyperframes@0.8.184 render --quality delivery --output renders/final.mp4

# 3. 交付检查
python3 <SKILL>/scripts/check_delivery.py --project <FILM>
```

真人录音走 `make_recording_kit.py` → 录 `recording/takes/<scene>-<NNN>.wav` → `import_recordings.py`；导入后不要跑 `tts.py`（它会拒绝覆盖 human manifest，除非 `--force`）。`tts.py` 的 provider：`auto` 先试 edge，失败后在 macOS 回退 `say`；`say` 用 `--voice Tingting` 等本机中文音色；`file` 用于外部 TTS/已有录音。正式片优先真人，TTS 只作为草稿或没有录音条件时的方案。

`hyperframes` 不可用时先 `npm i -g hyperframes@0.8.184` 或直接 `npx --yes hyperframes@0.8.184`。环境检查只报告，不自动安装系统软件。

## 参考文件

- [选题与受众](references/topic-and-audience.md)：什么值得讲、给谁讲、前提阶梯、标题与钩子、60 秒/90 秒/长片的范围。
- [研究与事实](references/research-and-facts.md)：来源等级、claim 台账、代码核验、数字与单位、时效、常见 CS 误区、类比边界。
- [叙事结构](references/story-structure.md)：从钩子到回扣的节拍、三种时长结构、转场与理解测试。
- [视觉语法](references/visual-grammar.md)：概念→画面的映射、10 种镜头、布局与动效规则、常见误导。
- [台词与配音](references/script-and-voice.md)：中文口播、术语首次出现、数字读法、TTS 词典、字幕与节奏。
- [真人旁白](references/human-voice.md)：为什么 TTS 有机器感、录音设备/表演、录音稿与导入、处理和验收。
- [声音](references/audio.md)：配乐情绪、音效设计、让位、响度与试听清单。
- [HyperFrames 制作](references/production.md)：工程契约、`data-*`、GSAP、字幕、字体、渲染与排错。
- [审片与交付](references/review-and-delivery.md)：四遍审阅、首帧、联系表、交付清单与封面。
- [案例：0.1 + 0.2](references/case-float.md)：一支完整片的方向、取舍、实测数据和可复现命令。
- `assets/template/`：可运行模板实验室风格、10 种镜头、字体、GSAP、音效）。
- `examples/float-0-1-0-2/`：完整示例工程与成片。
- `tests/`：脚本与构建回归；维护 skill 时运行 `python3 -m unittest discover -s tests`。

## 维护

- 模板改动先改 `assets/template/`，再把改动同步到 `examples/float-0-1-0-2/`（示例需要保留自己的 `film.json` 和 `evidence/`）。
- 新增镜头类型：在 `assets/template/lib/scenes.mjs` 加 renderer，在 `SCENES` 注册，补一条 CSS/快照测试，再更新 [视觉语法](references/visual-grammar.md)。
- 不把示例的事实、台词或数据当作通用模板；每个新片重新做台账。
