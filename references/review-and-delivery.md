# 审片与交付

自动检查只能证明文件、时长、响度和首帧；**文字是否好懂、画面是否误导、声音是否舒服，必须实际看和听。** 这一章是四遍审阅和一份交付清单。

## 四遍审阅

### 1. 事实审阅（看脚本，不看画面）

- 打开 `facts.json` 和 `SOURCES.md`，逐条对照脚本。
- 每条主张问：来源是 A 级吗？版本/平台写了吗？有没有把“通常”说成“总是”？
- 代码输出与 `evidence/verification.txt` 逐行对照；版本、语言、表达式一致吗？
- 类比的 `maps` 和 `breaks` 都在吗？`breaks` 有没有被片子说出来？
- 删掉任何无法追溯的句子。宁可少讲一句，不要多讲错一句。

### 2. 理解审阅（1× 看一遍，不暂停）

找一个人（或隔一小时后的自己），按正常速度看，不暂停。然后问：

1. 这支片在回答什么问题？
2. 机制第一步/最后一步是什么？
3. 用了什么类比？它在哪一步不成立？
4. 看完会改哪个写法/判断？
5. 哪一镜走神了？

- 只记住“浮点数不准” → 机制没讲清。
- 只记住类比，不记得机制 → 类比太重，回真实术语的段落太弱。
- 第 5 题指到的镜头，优先删/改。

### 3. 画面审阅（静帧 + 关键转场）

**联系表（1–2 fps）**：

```sh
ffmpeg -v error -y -i renders/final.mp4 \
  -vf "fps=1,scale=480:-1,tile=6x4:padding=4:margin=4" \
  -frames:v 5 stills/contact-%02d.jpg
```

看什么：

- 有没有连续 5 秒以上完全静止的画面？（hook 除外，但也要有微动/字幕变化）
- 有没有切点后 0.3 秒还空着的画面？
- 信息密度是否均匀？有没有一镜塞太满、下一镜太散？
- 色彩/版式是否统一？有没有突然变成另一个风格？

**关键转场（10 fps 条带）**：在每次切点前后各 1 秒抽 10 帧，看有没有黑帧、闪白、元素错位。

```sh
ffmpeg -v error -y -ss <cut-1> -t 2 -i renders/final.mp4 \
  -vf "fps=10,scale=480:-1,tile=5x4" -frames:v 1 stills/cut-<n>.jpg
```

**信息密集镜头全尺寸帧**：位字段、代码、对照卡、数字卡，按 1920×1080 看：

```sh
ffmpeg -v error -y -ss <t> -i renders/final.mp4 -frames:v 1 stills/full-<t>.png
```

检查：

- 正文 ≥ 24px；代码 ≥ 27px；字幕不挡页脚。
- 数字/单位/箭头方向正确；位宽比例真实；坐标轴有刻度。
- 代码输出与实际运行一致；没有伪造的 UI/数据。
- 画面上没有品牌、章节名或编号顶栏；页脚只放来源、口径等有效信息。
- 首帧：单独抽 `-ss 0` 的帧，必须是完整画面，不能是黑底/空卡。

### 4. 声音审阅（手机 + 耳机）

- 手机外放：每个字清楚吗？音乐有没有盖住辅音？
- 耳机：高频刺耳吗？低频糊吗？让位自然吗？
- 转场：whoosh 与切点对齐吗？有没有迟到/早到？
- 响度：`check_delivery.py` 的 LUFS / true peak 在范围内吗？
- 结尾：音乐淡出完整吗？

没有实际试听，就在交付说明里写“未试听”。不要写“声音已验收”。

## 自动检查

```sh
python3 scripts/check_content.py --project <FILM> --strict
python3 scripts/check_delivery.py --project <FILM> --video renders/final.mp4
npx --yes hyperframes@0.8.184 check
```

| 检查 | 能证明 | 不能证明 |
| --- | --- | --- |
| `check_content.py` | 结构、claim 映射、字号/字数警告、时间轴比例 | 事实是否正确、观众是否听懂 |
| `hyperframes check` | lint、运行时错误、布局、动效、对比度 | 叙事是否成立、声音是否舒服 |
| `check_delivery.py` | 文件、分辨率、时长、音轨、响度、首帧非空 | 内容质量、听感、平台适配 |
| `snapshot` | 指定时间的画面 | 动态节奏、转场、音频 |

自动检查通过不等于可以发布；它只是把“低级错误”挡在门外。

## 交付清单

一份可发布的交付至少包含：

- [ ] `renders/final.mp4`：1920×1080、30fps、H.264 + AAC、有声音、时长与 `timeline.json` 一致。
- [ ] 可复现工程：`film.json`、`timeline.json`、`build.mjs`、`lib/`、`assets/`、`index.html`、`compositions/`。
- [ ] `DIRECTION.md`：方向、三个角度、专属手法、镜头表。
- [ ] `SOURCES.md` + `facts.json`：来源、claim、核验方式、边界。
- [ ] `SCRIPT.md`：台词、屏幕字、读音备注。
- [ ] `stills/`：首帧、每个镜头一张关键帧、联系表、关键转场条带。
- [ ] `evidence/`：`verification.txt`、`timing.json`、`music.json`、`audio-mix.json`、`content-check.json`、`delivery.json`。
- [ ] 一句交付说明：哪些已验证、哪些没验证（例如“已试听手机外放；未在 B 站实际投放”）。

### 交付说明模板

```text
成片：renders/final.mp4（100.5s，1920×1080，30fps，H.264/AAC）
方向：A→C 混合；一句话主张是……
事实：10 条 claim，均为 verified；代码在 Python 3.14 / Node 24 / C / Java 实机跑过。
自动检查：content / hyperframes check / delivery 全部通过；LUFS -16.0，true peak -2.6 dBFS。
人工审阅：已按 1× 看两遍、手机外放试听一遍；未做平台上传测试。
已知限制：TTS 为 macOS Tingting，不是真人；竖版未适配。
```

## 封面

如果平台需要封面：

- 比例：16:9（横版）、4:3（B 站/信息流）、3:4（小红书/抖音）。
- 只用片中真实渲染的帧，不用无关素材或伪造 UI。
- 标题 ≤ 12 个汉字；副标题只补一个信息，不要重复标题。
- 主体在安全区内：竖版底部 15% 会被 UI 遮挡；横版右侧 10% 可能被裁。
- 首帧本身要能当缩略图；封面是在首帧基础上加字，不是另一套视觉。

模板没有内置封面生成器；用 `stills/` 的 1920×1080 帧，在设计工具里按比例重排。不要把横版直接裁成竖版：重新安排主体和字号。

## 归档与复现

- 目录名用 `YYYY-MM-DD-<slug>` 或 `<slug>`；不要用“final-final-2”。
- 保留 `film.json`、`timeline.json` 和生成脚本；只交 MP4 等于不可修改。
- 记录 HyperFrames 版本、Node/Python/FFmpeg 版本、TTS provider/voice、字体版本。
- 素材来源/许可放在 `SOURCES.md` 或 `ASSETS.md`；字体 OFL、GSAP 许可、音效来源分别记。
- 重新渲染前先 `node build.mjs`；只改音频时也要重建 `index.html` 的 `data-duration` 和音频引用。

## 发布前最后 60 秒

- 首帧完整吗？
- 前 3 秒有问题/结果吗？
- 字幕有没有错字/断数？
- 最后一帧有没有被切掉？
- 音轨在手机上有声吗？
- 来源/版本有没有写？
- 交付说明有没有夸大“已验证”的范围？
