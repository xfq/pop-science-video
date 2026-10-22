#!/usr/bin/env python3
"""Create a new CS explainer project from the skill's HyperFrames template.

  python3 scripts/init_project.py --output ~/films/why-0.1-plus-0.2
  python3 scripts/init_project.py --output ./film --from-film ./my-film.json --force
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL / "assets" / "template"


def blank_film() -> dict:
    def line(text, mark=None, pause=None):
        item = {"caption": text, "tts": text}
        if mark:
            item["mark"] = mark
        if pause is not None:
            item["pause"] = pause
        return item

    return {
        "meta": {
            "title": "待定标题：一个计算机问题",
            "slug": "replace-me",
            "language": "zh-CN",
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "audience": "对计算机好奇、但没有相关背景的观众",
            "targetSeconds": 75,
            "takeaway": "一句话说清这支片子要让观众带走什么。",
            "voice": {"provider": "auto", "voice": "Tingting", "rate": 180, "lexicon": {}},
        },
        "scenes": [
            {
                "id": "hook", "type": "hook", "chapter": "开场",
                "kicker": "先抛出一个具体问题",
                "a": "0.1", "b": "0.2", "result": "?", "note": "先别急着解释。",
                "bits": "0011111110111001100110011001100110011001100110011001100110011010",
                "hex": "0x3FB999999999999A", "footer": "把问题放进真实场景",
                "narration": [
                    line("用一个反直觉的问题开场。", "q"),
                    line("给出真实结果。", "result"),
                    line("这不是 bug。", "note"),
                ],
            },
            {
                "id": "pivot", "type": "statement", "chapter": "转折",
                "tag": "THE PIVOT", "line1": "先给结论。", "line2": "再给机制。",
                "sub": "用一句人话，把结论钉在观众脑子里。",
                "index": "01 — 问题的形状", "footer": "来源写在 facts.json",
                "narration": [line("先给结论，再解释为什么。", "line1"), line("结论必须能被一句话复述。", "line2"), line("所有语言都会给出同一个答案。", "sub")],
            },
            {
                "id": "mechanism", "type": "pipeline", "chapter": "机制",
                "kicker": "把机制拆成几步", "title": "它到底是怎么发生的？",
                "steps": [
                    {"label": "输入", "sub": "观众熟悉的一端", "note": "具体、可观察"},
                    {"label": "规则", "sub": "中间发生了什么", "note": "只讲必要的一步"},
                    {"label": "结果", "sub": "回到开头的问题", "note": "让因果闭合", "tone": "amber"},
                ],
                "foot": "每一步都要说清“因为什么，所以什么”。",
                "narration": [line("第一步。", "s0"), line("第二步。", "s1"), line("第三步。", "s2"), line("把因果闭合。", "foot")],
            },
            {
                "id": "recap", "type": "recap", "chapter": "小结",
                "kicker": "带走三件事", "title": "如果只记住三句话",
                "items": [
                    {"n": "01", "title": "第一句话", "note": "解释它为什么成立。", "code": "keep it concrete"},
                    {"n": "02", "title": "第二句话", "note": "给一个可执行的建议。", "code": "show the command"},
                    {"n": "03", "title": "第三句话", "note": "说清适用边界。", "code": "when not to use it"},
                ],
                "foot": "结论要能离开视频独立成立。",
                "narration": [line("第一条。", "r0"), line("第二条。", "r1"), line("第三条。", "r2"), line("结论要能独立成立。", "foot")],
            },
            {
                "id": "outro", "type": "outro", "chapter": "下期",
                "kicker": "留一个问题", "questionLines": ["下一个问题，", "比这个更有意思。"],
                "next": "下一期 · 待定", "teaser": "teaser()", "teaserValue": "下一个钩子",
                "sources": ["来源一", "来源二"],
                "narration": [line("把观众送到下一个问题。", "q0"), line("它到底长什么样？", "q1"), line("下期见。", "next")],
            },
        ],
    }


DIRECTION = """# DIRECTION

## 一句话
- 观众是谁：
- 看完能复述的一句话：
- 它为什么值得被讲：

## 理解路径
1. 观众现在以为什么：
2. 哪里会卡住：
3. 先给什么、后给什么：
4. 哪个类比能过桥：
5. 类比的边界在哪里：

## 三个候选角度
| 角度 | 钩子 | 视觉母题 | 风险 |
| --- | --- | --- | --- |
| A |  |  |  |
| B |  |  |  |
| C |  |  |  |

选定：A / B / C
理由：

## 专属手法（因为概念有 X，所以画面用 Y）
1.
2.
3.

## 画面规范
- 画幅 / 时长 / 帧率：
- 字体与字号：
- 色彩与语义：
- 动效节奏：
- 字幕位置：

## 镜头表
| # | 时间 | 画面 | 旁白要说的意思 | 标记 / 动效 | 事实来源 |
| --- | --- | --- | --- | --- | --- |
| 1 |  |  |  |  |  |

## 不做什么
-
"""

SOURCES = """# SOURCES

每条事实都要能追溯到下面的一行；视频里的 `footer` 只放最必要的一条。

| id | 主张 | 类型 | 来源 | 链接 | 访问日期 | 核验方式 |
| --- | --- | --- | --- | --- | --- | --- |
| c1 |  | 规范 / 论文 / 官方文档 / 教材 |  |  |  | 实机运行 / 原文核对 |
"""

FACTS = {
    "claims": [
        {
            "id": "c1",
            "claim": "把一条可验证的主张写在这里。",
            "status": "needs-review",
            "sources": [{"title": "来源标题", "url": "https://example.com", "kind": "primary", "accessed": "YYYY-MM-DD"}],
            "verification": "说明你是怎么核对的：实机运行、原文哪一节、谁复现过。",
            "caveat": "适用边界或版本条件。",
        }
    ],
    "analogies": [
        {
            "text": "这里用的类比",
            "maps": "它对应机制的哪一部分",
            "breaks": "它在哪一步不再成立",
        }
    ],
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output", required=True, type=Path, help="new project directory")
    ap.add_argument("--from-film", type=Path, help="copy an existing film.json into the new project")
    ap.add_argument("--force", action="store_true", help="write into a non-empty directory, keeping its film.json")
    args = ap.parse_args()

    out = args.output.expanduser().resolve()
    if not TEMPLATE.exists():
        raise SystemExit(f"template missing: {TEMPLATE}")
    if out.exists() and any(out.iterdir()) and not args.force:
        raise SystemExit(f"{out} is not empty. Pass --force to add the template files without deleting content.")
    out.mkdir(parents=True, exist_ok=True)

    # Copy the engine, but never overwrite a user's film or generated renders.
    ignore = shutil.ignore_patterns("node_modules", ".hyperframes", "renders", "stills", "film.json", "index.html",
                                    "build-report.json", "compositions")
    shutil.copytree(TEMPLATE, out, dirs_exist_ok=True, ignore=ignore)
    (out / "compositions").mkdir(exist_ok=True)
    for sub in ("assets/tts", "audio-chunks", "renders", "stills", "evidence", "recording/takes"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    (out / "recording" / "takes" / ".gitkeep").touch()

    film_path = out / "film.json"
    if args.from_film:
        shutil.copyfile(args.from_film.expanduser().resolve(), film_path)
    elif not film_path.exists():
        film_path.write_text(json.dumps(blank_film(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    for name, content in (("DIRECTION.md", DIRECTION), ("SOURCES.md", SOURCES)):
        target = out / name
        if not target.exists():
            target.write_text(content, encoding="utf-8")
    facts = out / "facts.json"
    if not facts.exists():
        facts.write_text(json.dumps(FACTS, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"created {out}")
    print("next:")
    print(f"  1. edit {film_path.name}, DIRECTION.md, SOURCES.md, facts.json")
    print(f"  2. cd {out} && python3 {SKILL / 'scripts/check_content.py'} --project .")
    print(f"  3. python3 {SKILL / 'scripts/check_environment.py'} --project .")
    print(f"  4. node build.mjs")


if __name__ == "__main__":
    main()
