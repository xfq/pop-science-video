# 为什么 0.1 + 0.2 不等于 0.3

一支 100.5 秒的计算机科普片，演示 `pop-science-video` 的完整流程：
事实台账 → 三幕叙事 → 位字段/终端/数字卡 → 中文旁白 → 原创配乐与混音 → HyperFrames 渲染。

| | |
| --- | --- |
| 成片 | `renders/final.mp4`（1920×1080，30fps，H.264/AAC） |
| 时长 | 100.5s |
| 旁白 | 33 句，macOS `say`（Tingting），83.94s 语音 |
| 字幕 | 34 条 |
| 事实 | 10 条 claim，全部 verified；4 语言实机输出 |
| 混音 | −16.0 LUFS，true peak −2.6 dBFS |
| 检查 | `hyperframes check` 通过；152/152 对比度 |
| 方向 | [DIRECTION.md](DIRECTION.md) |
| 台词 | [SCRIPT.md](SCRIPT.md) |
| 来源 | [SOURCES.md](SOURCES.md) / [facts.json](facts.json) |
| 复盘 | [../../references/case-float.md](../../references/case-float.md) |

## 重新生成

```sh
# 从 skill 根目录
python3 ../../scripts/check_content.py --project .
python3 ../../scripts/tts.py --project .            # 本机 edge 403 -> say
python3 ../../scripts/make_timeline.py --project .
python3 ../../scripts/music.py --project . --mood curious
python3 ../../scripts/mix_audio.py --project .
node build.mjs
npx --yes hyperframes@0.8.184 check
npx --yes hyperframes@0.8.184 render --quality delivery --output renders/final.mp4
python3 ../../scripts/check_delivery.py --project .
```

只改文案时：改 `film.json` → `tts.py`（增量）→ `make_timeline.py` → `mix_audio.py` → `build.mjs` → render。
只改画面时：改 `film.json` 的视觉字段或 `lib/` → `build.mjs` → snapshot/check → render。

## 事实

- `0.1 + 0.2 = 0.30000000000000004`：Python 3.14、Node 24、C（clang）、Java 实机一致。
- 0.1 的 binary64 位模式：`0011111110111001100110011001100110011001100110011001100110011010` / `0x3FB999999999999A`。
- `0.1` 的精确存储值：`0.1000000000000000055511151231257827021181583404541015625`。
- 与 0.3 的差：`5.551115123125783e-17`，约 1 ulp（near 0.3 的间距 2⁻⁵⁴）。
- 命令与完整输出：`evidence/verification.txt`。

## 换成真人旁白

当前旁白是 macOS `say`（Tingting），机器感明显。逐句录音稿已经导出在 [recording/NARRATION.md](recording/NARRATION.md)。如果暂时不能录，可以先听 [recording/auditions/index.md](recording/auditions/index.md) 里的本机音色对比（Tingting / Meijia / Flo / Reed）。

```sh
# 录好的文件放进 recording/takes/，命名如 hook-000.wav
python3 ../../scripts/import_recordings.py --project .
python3 ../../scripts/make_timeline.py --project .
python3 ../../scripts/mix_audio.py --project .
node build.mjs
npx --yes hyperframes@0.8.184 render --quality delivery --output renders/final.mp4
```

时间轴会按真实语速重排；完整录音/表演/处理说明见 [human-voice.md](../../references/human-voice.md)。

## 已知限制

- 旁白是 macOS `say`，不是真人；正式发布建议换真人录音。
- 只做了 16:9；竖版未适配。
- 配乐是 numpy 合成的 bed，不是商业编曲；可换用户提供的音乐。
- 未做平台上传测试；发布前按 [审片与交付](../../references/review-and-delivery.md) 再看一遍首帧/字幕/声音。
