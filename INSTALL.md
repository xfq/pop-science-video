# 安装与使用

这个仓库本身就是一个 agent skill。安装 = 把**包含 `SKILL.md` 的整个文件夹**放到 agent 会扫描的 skills 目录，文件夹名用 `pop-science-video`。

## 1. 安装

### 方式 A：一条命令（推荐）

在仓库根目录：

```bash
mkdir -p ~/.agents/skills && ln -sfn "$PWD" ~/.agents/skills/pop-science-video
```

然后重开会话。

也可以用标准的 skills CLI：

```bash
npx skills add "$PWD" --skill pop-science-video --agent universal -g -y
```

Claude Code 把 `universal` 换成 `claude-code`。

### 方式 B：install.sh（复制/备份/离线）

```bash
./install.sh        # 或 bash install.sh（下载 ZIP 后可能没有执行位）
```

默认复制到：

```text
~/.agents/skills/pop-science-video
```

DeepSeek Harness、Codex 和大多数支持 Agent Skills 的工具都扫描 `~/.agents/skills/`。Claude Code 用另一个目录：

```bash
./install.sh --target ~/.claude/skills/pop-science-video
```

两种都装：

```bash
./install.sh
./install.sh --target ~/.claude/skills/pop-science-video
```

### 方式 C：开发模式（install.sh 的链接）

```bash
./install.sh --link
```

等价于上面的 `ln -sfn`，只是多了备份/校验。删掉仓库链接就断，正式分发用复制模式。

### Windows

`install.sh` 需要 bash。Windows 可以在 WSL / Git Bash 里运行，或直接手动复制到：

```text
%USERPROFILE%\.agents\skills\pop-science-video
```

依赖用 Windows 版 Node.js、FFmpeg、Python；没有 macOS `say` 时，旁白用真人录音、edge-tts 或外部 TTS 导出文件，走同一个 `import_recordings.py`。

### 方式 C：手动复制

```bash
mkdir -p ~/.agents/skills
cp -R /path/to/xfq-popular-science-skill ~/.agents/skills/pop-science-video
```

Claude Code：

```bash
mkdir -p ~/.claude/skills
cp -R /path/to/xfq-popular-science-skill ~/.claude/skills/pop-science-video
```

### 安装内容与体积

默认复制会排除生成媒体（示例 MP4、stills、TTS WAV、mix/music），安装后约 20 MB；模板、脚本、references、示例的 `film.json`/事实/来源/录音稿都在。

需要把示例成片和静帧也装进去：

```bash
./install.sh --with-media
```

### 发布后用 skills CLI

仓库发布到 GitHub 后：

```bash
npx skills add <github-repo> --skill pop-science-video
```

本地未发布时用上面的 `install.sh` 或手动复制，不要用占位 URL。

## 2. 验证安装

```bash
ls -la ~/.agents/skills/pop-science-video/SKILL.md
head -8 ~/.agents/skills/pop-science-video/SKILL.md
```

应该看到 frontmatter：

```yaml
---
name: pop-science-video
description: ...
---
```

再跑环境检查（不会自动装软件）：

```bash
python3 ~/.agents/skills/pop-science-video/scripts/check_environment.py --skip-hyperframes
```

需要的依赖：

| 依赖 | 用途 | 检查 |
| --- | --- | --- |
| Node.js ≥ 22 | `build.mjs`、HyperFrames CLI | `node -v` |
| FFmpeg / ffprobe | 音频、编码、交付检查 | `ffmpeg -version` |
| Chrome | HyperFrames 逐帧渲染 | 安装 Chrome |
| Python ≥ 3.9 + numpy | 时间轴、音乐、混音、检查 | `python3 -c "import numpy"` |
| edge-tts（可选） | 在线 TTS；失败回退 `say` | `pip install edge-tts` |
| Pillow（可选） | 首帧统计 | `pip install Pillow` |
| 真人录音（推荐） | 正式片旁白 | 手机/麦克风 |
| macOS `say`（可选） | 本地 TTS 草稿 | 仅 macOS；其他系统用 edge/file |

```bash
python3 -m pip install -r ~/.agents/skills/pop-science-video/requirements.txt
```

HyperFrames 不需要单独 clone；`npx --yes hyperframes@0.8.184` 会拉取并缓存。离线时：

```bash
npm i -g hyperframes@0.8.184
```

## 3. 让 agent 读取 skill

安装/更新后**重新打开会话**（或让工具重新加载 skills）。新 skill 不会自动注入已经开着的上下文。

然后在对话里明确点名：

```text
用 pop-science-video，把“为什么 DNS 查询通常这么快”做成一支 90 秒中文横版科普片。
先给我事实、叙事角度和镜头表，确认后再配音和渲染。
```

Codex 里可以写 `$pop-science-video`；Claude Code 里可以直接说 skill 名。关键是**说清主题、受众、时长、画幅、语言**，以及“先看方案还是直接做”。

## 4. 第一次做片

### 4.1 建独立工程

不要在 skill 目录里做片。工程放在 `~/films/` 或项目仓库里：

```bash
SKILL=~/.agents/skills/pop-science-video
python3 "$SKILL/scripts/init_project.py" --output ~/films/why-dns-is-fast
python3 "$SKILL/scripts/check_environment.py" --project ~/films/why-dns-is-fast
```

生成：

```text
~/films/why-dns-is-fast/
  film.json          # 片：台词 + 视觉数据
  DIRECTION.md       # 方向/镜头表
  SOURCES.md         # 来源
  facts.json         # claim 台账
  build.mjs          # 生成 HyperFrames 工程
  assets/            # 字体/GSAP/音效
  recording/takes/   # 真人录音放这里
```

### 4.2 写内容

最少改四个文件：

- `film.json`：每个 scene 的旁白、mark、视觉字段。
- `DIRECTION.md`：一句话主张、三个角度、选定理由、专属手法、镜头表。
- `facts.json`：每条 claim 的来源、核验、边界。
- `SOURCES.md`：人读的来源表。

如果让 agent 做，它应该先写这四份，再写代码；不要直接开始做动画。

检查内容：

```bash
python3 "$SKILL/scripts/check_content.py" --project ~/films/why-dns-is-fast --strict
```

### 4.3 旁白：真人优先

```bash
python3 "$SKILL/scripts/make_recording_kit.py" --project ~/films/why-dns-is-fast
# 按 recording/NARRATION.md 逐句录，放进 recording/takes/
# 文件名必须是 hook-000.wav、pivot-002.wav 这种
python3 "$SKILL/scripts/import_recordings.py" --project ~/films/why-dns-is-fast
```

没有录音条件才用 TTS：

```bash
python3 "$SKILL/scripts/tts.py" --project ~/films/why-dns-is-fast
```

想先去掉机器音、出“音乐 + 字幕”预览：

```bash
python3 "$SKILL/scripts/mix_audio.py" --project ~/films/why-dns-is-fast --mute-voice
```

详细说明：[references/human-voice.md](references/human-voice.md)。

### 4.4 时间轴、音乐、混音

```bash
python3 "$SKILL/scripts/make_timeline.py" --project ~/films/why-dns-is-fast
python3 "$SKILL/scripts/music.py" --project ~/films/why-dns-is-fast --mood curious
python3 "$SKILL/scripts/mix_audio.py" --project ~/films/why-dns-is-fast
```

`make_timeline.py` 会按真实语音时长重排镜头/字幕/mark；不要手改 `timeline.json`。`music.py` 可换 `focused` / `playful` / `tense`；`mix_audio.py` 默认 −16 LUFS。

### 4.5 生成、检查、渲染

```bash
cd ~/films/why-dns-is-fast
node build.mjs
npx --yes hyperframes@0.8.184 check
npx --yes hyperframes@0.8.184 snapshot --at 8,30,55,80
npx --yes hyperframes@0.8.184 render --quality delivery --output renders/final.mp4
```

先渲 8–12 秒草稿确认动态/字幕/声音，再渲全片。`check` 必须通过；`snapshot` 要逐张看全尺寸帧。

### 4.6 交付检查

```bash
python3 "$SKILL/scripts/check_delivery.py" --project ~/films/why-dns-is-fast
```

它检查文件、分辨率、时长、音轨、响度、首帧非空；不替代实际观看/试听。

产物：

```text
renders/final.mp4       成片
stills/                 关键帧/联系表
evidence/               核验、时间轴、混音、检查报告
recording/NARRATION.md  录音稿
```

### 4.7 改台词

已有工程改词不需要重跑整条链，只改 `film.json` 的 `narration[]`，然后：

```bash
python3 "$SKILL/scripts/revise.py" --project ~/films/why-dns-is-fast
```

它会只重录 `tts` 变了的句子，重排时间轴、按需重做配乐、混音、构建，并检查 mark/时长/响度和构建警告。加 `--render draft` 出草稿，`--render delivery` 出正式片；两者渲染前都会跑 `hyperframes check`，正式片渲染后还会跑交付检查。真人录音先不带 `--import` 跑一次看要重录/改名的 take，录完再加 `--import`。

## 5. 日常使用提示

- **主题要具体**：“为什么 0.1 + 0.2 不等于 0.3”比“浮点数科普”好做。
- **先要方向**：让 agent 先给三个角度 + 镜头表，确认后再动画/配音。
- **事实先行**：要求它跑代码、给来源、标 `caveat`；不要接受“网上都这么说”。
- **旁白优先真人**：TTS 只做草稿；用 `audition_voices.py` 试听也比默认 Tingting 好。
- **一次只改一层**：先文案，再画面，再声音；改台词用 `revise.py`，它会按需重跑对应脚本。
- **别把工程放 skill 里**：升级/重装 skill 不会碰你的片子。

## 6. 更新与卸载

更新（手动复制安装）：

```bash
cd /path/to/xfq-popular-science-skill
git pull --ff-only          # 或重新下载
./install.sh --force        # 旧目录会备份为 .bak.<时间戳>
```

更新（链接安装）：

```bash
cd /path/to/xfq-popular-science-skill && git pull --ff-only
```

卸载：

```bash
rm -rf ~/.agents/skills/pop-science-video
# 或 Claude Code:
rm -rf ~/.claude/skills/pop-science-video
```

卸载不会删除你的 `~/films/` 工程。

## 7. 常见问题

| 问题 | 原因 | 解决 |
| --- | --- | --- |
| agent 不认这个 skill | 没有重开会话，或目录里没有 `SKILL.md` | 重开会话；确认 `~/.agents/skills/pop-science-video/SKILL.md` |
| skill 名不对 | 文件夹名不是 `pop-science-video` | 重命名文件夹（frontmatter 的 `name` 也要一致） |
| `npx` 报 EPERM / cache 权限 | `~/.npm` 属主问题 | `npm config get cache`；修权限，或 `export npm_config_cache=/tmp/npm-cache` |
| `hyperframes@latest` 找不到版本 | registry 的 latest 标签暂时指向未发布版本 | 用固定的 `hyperframes@0.8.184` |
| Node 版本太低 | HyperFrames 要求 Node ≥ 22 | `nvm install 22` / 升级 Node |
| 渲染没有声音 | `assets/mix.wav` 缺失或 `index.html` 没重建 | 先 `mix_audio.py`，再 `node build.mjs`，再渲染 |
| 中文字体不对 | 字体文件没复制 | 确认 `assets/fonts/NotoSansSC.woff2` 存在 |
| 真人录音导入缺句 | 文件名不匹配 | 看 `recording/NARRATION.md` 的精确文件名；跑 `import_recordings.py --dry-run` |
| 录音太小声/削顶 | 输入电平不对 | 重录；峰值控制在 −12 到 −6 dBFS |
| 导入后时间轴变长 | 真人语速比 TTS 慢 | 正常；删词/重录，而不是 1.5× 变速 |

## 8. 许可

- 代码、文档、模板、原创音效：MIT（`LICENSE`）。
- 字体：OFL（`assets/template/assets/fonts/`）。
- GSAP：GreenSock 标准许可（`THIRD_PARTY.md`）。
- HyperFrames：第三方工具，按自身许可使用。
- 示例中的事实/来源只用于演示；每个新片重新做台账。
