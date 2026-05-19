#!/usr/bin/env python3
"""Render wx-summary-skill webpages through the newspaper layout pipeline.

This bridges:
  summary.json + analysis.json
      -> newspaper/story.json + layout-plan.json + themed image cards
      -> local newspaper renderer
      -> range-scoped site/dist output

It keeps the target newspaper layout engine as the final HTML renderer so the
wx-summary-skill webpage mode matches the group-daily-newspaper output shape
instead of the older single-page digest template.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import random
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from site_branding import build_branding_head, inject_branding_head
from vendor_render_newspaper import render as render_newspaper_html

CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
PDFINFO = shutil.which("pdfinfo")

FONT_SERIF_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/Supplemental/STSong.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/simkai.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
]
FONT_SANS_CANDIDATES = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
FONT_LATIN_CANDIDATES = [
    "/System/Library/Fonts/Times.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/opentype/urw-base35/NimbusRoman-Regular.otf",
    "C:/Windows/Fonts/times.ttf",
]


PRESETS: dict[str, dict[str, Any]] = {
    "44137533350@chatroom": {
        "accent": "#8f2f25",
        "dark": "#1f1915",
        "masthead": {
            "name_top": "Christina AI+",
            "name_bot": "知识圈周报",
            "pinyin": "CHRISTINA AI+ · WEEKLY",
            "slogan_cn_html": "工 具 · 流 程 · 排 障<br>把 AI 新 玩 具 变 成 真 工 作",
            "promo_tag": "Weekly Newspaper · Legacy Pipeline Restored",
            "publisher": "Christina的AI+ 知识圈出版",
            "issue_code": "代号 C-AI+",
            "footer_brand": "Christina AI+ · WEEKLY",
        },
        "lead_title": "把 AI 工 具 用 成 群 内 问 诊 台\n一 周 都 在 现 场 排 障 与 交 付",
        "page2_name": "工 具 台 账 · 实 战 室",
        "page3_name": "副 刊 · 格 式 与 交 付",
        "page5_name": "共 建 · Codex 修 理 间",
        "page6_name": "尾 版 · 微 信 生 态",
        "page2_person": "Christina",
        "page5_person": "凌镜",
        "sops": [
            {
                "title": "先把生图入口和版本说清楚",
                "author": "Christina / 凌镜",
                "time": "05-11",
                "steps": [
                    "别只说“Gemini 不准”，先确认你走的是哪个入口，是 Gemini、Flow 还是 Veo。",
                    "把模型版本、额度、排队情况放在同一张表里比较，再判断问题来自模型还是链路。",
                    "需要高频出图时，先找稳定入口，再谈提示词精修。",
                    "群里讨论模型时，尽量附上你实际使用的页面或产品名。 ",
                ],
                "output": "把“模型听起来一样”拆成“入口、版本、额度、速度”四个可核对维度。",
            },
            {
                "title": "Codex 从 API 切订阅前先做一轮会话保全",
                "author": "Christina / 小茗同学.（冬眠）",
                "time": "05-15",
                "steps": [
                    "确认当前 `model_provider` 字段大小写是否一致，尤其留意 `OpenAI` / `openai`。",
                    "切订阅前先备份本地 SQLite 和聊天目录，不要等看不到 session 再补救。",
                    "迁移后先验证历史记录过滤条件，再继续改登录方式或中转链路。",
                    "排障时把“记录没了”和“只是被过滤了”分开处理。",
                ],
                "output": "先保住本地会话，再解决提供商字段和过滤逻辑造成的“假丢失”。",
            },
            {
                "title": "把建站与微信接入拆成最短交付链路",
                "author": "Christina / 千逐",
                "time": "05-15",
                "steps": [
                    "先找一个对标站，让 Codex 学排版、文字节奏和基础动效。",
                    "先在内置浏览器里做初版，再通过局部反馈一点点压细节。",
                    "真要接入微信或群聊，再单独处理登录、消息同步和风控问题。",
                    "讨论 HTML、Markdown、JSON 时，先分清是给人看还是给 AI 看。",
                ],
                "output": "先把可展示页面做出来，再把微信链路和自动化能力一层层接上去。",
            },
        ],
        "qas": [
            {
                "q": "Gemini 生图慢又不准时，第一步该查什么？",
                "asker": "Ljorl / 群内追问",
                "answers": [
                    {"who": "Christina", "text": "先核对是不是走在正确入口上，Flow 和普通 Gemini 页面体验差异很大。"},
                    {"who": "凌镜", "text": "还要看背后到底是哪个 Nano Banana 版本，版本不对，质量判断会完全跑偏。"},
                ],
            },
            {
                "q": "Codex 从 API 换订阅后历史记录没了怎么办？",
                "asker": "Christina",
                "answers": [
                    {"who": "Christina", "text": "先检查 `model_provider` 的大小写是否让旧 session 被过滤掉了。"},
                    {"who": "小茗同学.（冬眠）", "text": "如果本地文件还在，优先按数据过滤问题处理，不要第一反应重装。"},
                ],
            },
            {
                "q": "重启后 Codex 提示无法设置管理者沙盒，还要不要重装？",
                "asker": "嫑忈",
                "answers": [
                    {"who": "Christina", "text": "能修先修，本地聊天记录通常还在对应目录里，不必一上来清空。"},
                    {"who": "群内经验流", "text": "先确认聊天目录和登录态，再决定是 Claude Code 修还是最后手段重装。"},
                ],
            },
        ],
    },
    "43663749608@chatroom": {
        "accent": "#243a61",
        "dark": "#181c24",
        "masthead": {
            "name_top": "IGN AI",
            "name_bot": "洋来周报",
            "pinyin": "IGN AI · YANGLAI WEEKLY",
            "slogan_cn_html": "群 聊 · 开 工 · 折 腾<br>把 工 具 流 行 变 成 实 际 工 作",
            "promo_tag": "Legacy Newspaper Flow · Weekly Archive",
            "publisher": "IGN AI | 洋来群出版",
            "issue_code": "代号 IGN-7D",
            "footer_brand": "IGN AI | 洋来周报 · WEEKLY",
        },
        "lead_title": "工 具 混 战 里 长 出 来 的 学 生 Builder 周\n账 号、token、活 动 与 电 脑 预 算 挤 在 同 一 张 工 作 台",
        "page2_name": "压 缩 机 · 情 报 站",
        "page3_name": "副 刊 · 工 具 变 形 记",
        "page5_name": "共 建 · 学 生 Builder",
        "page6_name": "尾 版 · 线 下 与 知 识 库",
        "page2_person": "管家",
        "page5_person": "清九半斛 赵春昊",
        "sops": [
            {
                "title": "先按场景，而不是按品牌选工具",
                "author": "千逐 / 群内工具混战",
                "time": "05-04",
                "steps": [
                    "先分清是日常问答、开发协作、移动端生活助手，还是需要浏览器或远控。",
                    "再比较 Codex、Claude、Trae、豆包各自在哪个场景最顺手，而不是直接问谁最强。",
                    "遇到体验问题时把客户端、模型、登录方式和是否走中转站一起报出来。",
                    "别让“别人说强”替代你的实际工作流测试。",
                ],
                "output": "把抽象的模型争论压成“我的场景该用哪一栈”的选择题。",
            },
            {
                "title": "登录、接码和中转站要单独列成资源层",
                "author": "杭州大四学生Kiki / 清九半斛 赵春昊",
                "time": "05-05",
                "steps": [
                    "先决定你是走 ChatGPT 登录、API 登录还是中转站。",
                    "首次登录需要手机号或接码时，提前确认 WhatsApp 渠道与 refresh token 链路。",
                    "把中转站、token、接码平台当成单独资源管理，不要混进工具本体讨论里。",
                    "切换客户端前先确认自己能否稳定续用当前账号与额度。",
                ],
                "output": "把“能不能用”从模型能力里拆出来，单独处理账号与入口门槛。",
            },
            {
                "title": "低预算学生 builder 先保工作流，再谈本地自由",
                "author": "羽升 / 千逐 / 马宇航",
                "time": "05-08",
                "steps": [
                    "先确认你的预算是为了跑 Cursor、Agent、CLI 和日常工具，还是为了本地部署模型。",
                    "3000-6000 预算优先保内存、续航和能否同时开多个工作窗口。",
                    "如果真想本地部署，先接受“小模型可玩，大模型不自由”的现实。",
                    "活动报名、黑客松、线下交流和二手设备渠道，往往比盲目追求 token 自由更值。 ",
                ],
                "output": "先让设备撑住真实作业链路，而不是为一个想象中的本地全能方案买单。",
            },
        ],
        "qas": [
            {
                "q": "Codex、Claude、Trae、豆包到底该怎么选？",
                "asker": "群内高频问题",
                "answers": [
                    {"who": "千逐", "text": "先按任务选，不要先按信仰选。开发、远控、移动端、生活助手根本不是同一类场景。"},
                    {"who": "群内共识", "text": "这周没有赢家，只有按场景换栈。"},
                ],
            },
            {
                "q": "ChatGPT / Codex 登录要美国卡或者手机号时怎么办？",
                "asker": "是小何马 数媒 师大 22 级",
                "answers": [
                    {"who": "杭州大四学生Kiki", "text": "先把 WhatsApp 接码、refresh token 和首次登录链路分开看。"},
                    {"who": "清九半斛 赵春昊", "text": "中转站、token 和客户端别混为一谈，先确认你到底卡在哪一层。"},
                ],
            },
            {
                "q": "3000 到 6000 预算能不能直接实现本地部署自由？",
                "asker": "羽升 / 慢慢🌙²",
                "answers": [
                    {"who": "千逐", "text": "别把预算先烧在幻想里，先让机器顶住你真实的学习和开发窗口。"},
                    {"who": "马宇航 湖科大(小马哥）", "text": "小模型可以玩，大模型要真舒服，内存和成本会立刻上去。"},
                ],
            },
        ],
    },
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


_FONT_CACHE: dict[tuple[str, int], ImageFont.ImageFont] = {}


def first_existing(paths: list[str]) -> str | None:
    for candidate in paths:
        if Path(candidate).exists():
            return candidate
    return None


def font(kind: str, size: int) -> ImageFont.ImageFont:
    mapping = {
        "serif": FONT_SERIF_CANDIDATES,
        "sans": FONT_SANS_CANDIDATES,
        "latin": FONT_LATIN_CANDIDATES,
    }
    key = (kind, size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    resolved = first_existing(mapping[kind])
    if resolved:
        try:
            loaded = ImageFont.truetype(resolved, size)
            _FONT_CACHE[key] = loaded
            return loaded
        except OSError:
            pass

    loaded = ImageFont.load_default()
    _FONT_CACHE[key] = loaded
    return loaded


def smart_split(text: str, target: int = 15) -> tuple[str, str]:
    text = re.sub(r"\s+", "", text.strip())
    if len(text) <= target:
        return text, ""
    candidates = [i for i, ch in enumerate(text) if ch in "，。；：、|丨·/—-"]
    if candidates:
        mid = len(text) / 2
        idx = min(candidates, key=lambda i: abs(i - mid))
        return text[: idx + 1], text[idx + 1 :]
    idx = min(max(target, len(text) // 2), len(text) - 1)
    return text[:idx], text[idx:]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    raw_lines = text.splitlines() or [text]
    for raw in raw_lines:
        buf = ""
        for ch in raw:
            test = buf + ch
            width = draw.textbbox((0, 0), test, font=fnt)[2]
            if width <= max_width or not buf:
                buf = test
            else:
                lines.append(buf)
                buf = ch
        if buf:
            lines.append(buf)
    return lines or [text]


def draw_multiline(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    fill: str,
    line_gap: int = 8,
) -> int:
    x1, y1, x2, y2 = box
    max_width = x2 - x1
    lines = wrap_text(draw, text, fnt, max_width)
    y = y1
    for line in lines:
        draw.text((x1, y), line, font=fnt, fill=fill)
        bbox = draw.textbbox((x1, y), line, font=fnt)
        y += (bbox[3] - bbox[1]) + line_gap
        if y > y2:
            break
    return y


def fake_qr(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], seed: str) -> None:
    x1, y1, x2, y2 = box
    size = min(x2 - x1, y2 - y1)
    cell = max(size // 29, 6)
    grid = 29
    width = cell * grid
    ox = x1 + ((x2 - x1) - width) // 2
    oy = y1 + ((y2 - y1) - width) // 2
    rnd = random.Random(int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16))
    draw.rectangle([ox, oy, ox + width, oy + width], fill="#ffffff", outline="#000000", width=3)
    for gy in range(grid):
        for gx in range(grid):
            finder = (
                (gx < 7 and gy < 7)
                or (gx >= grid - 7 and gy < 7)
                or (gx < 7 and gy >= grid - 7)
            )
            if finder:
                continue
            if rnd.random() > 0.53:
                draw.rectangle(
                    [
                        ox + gx * cell,
                        oy + gy * cell,
                        ox + (gx + 1) * cell,
                        oy + (gy + 1) * cell,
                    ],
                    fill="#000000",
                )
    for fx, fy in [(0, 0), (grid - 7, 0), (0, grid - 7)]:
        px = ox + fx * cell
        py = oy + fy * cell
        draw.rectangle([px, py, px + 7 * cell, py + 7 * cell], fill="#000000")
        draw.rectangle([px + cell, py + cell, px + 6 * cell, py + 6 * cell], fill="#ffffff")
        draw.rectangle([px + 2 * cell, py + 2 * cell, px + 5 * cell, py + 5 * cell], fill="#000000")


def make_canvas(width: int, height: int, bg: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (width, height), bg)
    return img, ImageDraw.Draw(img)


def short_group_name(group_name: str) -> str:
    if "Christina" in group_name:
        return "Christina AI+"
    if "IGN AI" in group_name:
        return "IGN AI"
    return re.sub(r"[@|丨·•_]", " ", group_name).strip()


def pick_preset(summary: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    gid = summary.get("group_id") or analysis.get("group_id") or ""
    return PRESETS.get(gid, {})


def build_quote_pool(summary: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, str]]:
    pool: list[dict[str, str]] = []
    for q in summary.get("quotes", []):
        pool.append({"text": q["text"], "who": q["who"], "cite": q["who"]})
    for cand in analysis.get("quote_candidates", [])[:12]:
        quoted = cand.get("quote_context", {}).get("quoted_preview") or ""
        reply = cand.get("quote_context", {}).get("reply_preview") or ""
        text = quoted if 6 <= len(quoted) <= 42 else reply
        text = re.sub(r"\s+", " ", text).strip(" \"'—")
        if not text:
            continue
        pool.append({"text": text, "who": cand.get("sender", "群成员"), "cite": f"{cand.get('sender','群成员')} · {cand.get('time','')[-5:]}"})
    dedup: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in pool:
        key = item["text"]
        if key in seen:
            continue
        seen.add(key)
        dedup.append(item)
    return dedup


def choose_person(people: list[dict[str, Any]], preferred_name: str | None, fallback_index: int) -> dict[str, Any]:
    if preferred_name:
        for person in people:
            if person["name"] == preferred_name:
                return person
    if people:
        idx = min(max(fallback_index, 0), len(people) - 1)
        return people[idx]
    return {"name": "群成员", "tag": "活跃成员", "desc": "本周持续参与群聊讨论。"}


def build_story(summary: dict[str, Any], analysis: dict[str, Any], preset: dict[str, Any]) -> dict[str, Any]:
    people = summary.get("people", [])
    threads = summary.get("main_threads", [])
    quote_pool = build_quote_pool(summary, analysis)
    q_index = 0
    timeline = []
    for idx, thread in enumerate(threads):
        cast = []
        if people:
            window = min(5, len(people))
            for j in range(window):
                cast.append({"name": people[(idx + j) % len(people)]["name"]})
        thread_quotes = []
        take = 2 if idx < 2 else 1
        for _ in range(take):
            if quote_pool:
                thread_quotes.append(
                    {
                        "text": quote_pool[q_index % len(quote_pool)]["text"],
                        "who": quote_pool[q_index % len(quote_pool)]["who"],
                    }
                )
                q_index += 1
        timeline.append(
            {
                "title": thread["title"],
                "story": thread["summary"],
                "quotes": thread_quotes,
                "cast": cast,
            }
        )

    date_label = analysis.get("date_range", {}).get("until") or summary.get("time_range", "").split("~")[-1].strip()
    opening = summary.get("opening") or summary.get("subheadline") or summary.get("headline") or ""
    lead_title = preset.get("lead_title")
    if not lead_title:
        line1, line2 = smart_split(summary.get("headline", "群聊周报"))
        lead_title = line1 if not line2 else f"{line1}\n{line2}"

    highlights = []
    top_senders = analysis.get("top_senders", [])
    sender_lookup = {item.get("name"): item.get("count") for item in top_senders}
    for person in people[:8]:
        tag = person.get("tag", "")
        if not tag and person["name"] in sender_lookup:
            tag = f"{sender_lookup[person['name']]} 条 / 活跃成员"
        highlights.append(
            {
                "name": person["name"],
                "tag": tag,
                "desc": person.get("desc", ""),
            }
        )

    char_count = analysis.get("char_count") or 0
    footer_quote = next((q for q in summary.get("quotes", []) if 8 <= len(q["text"]) <= 32), None)
    if not footer_quote and summary.get("quotes"):
        footer_quote = summary["quotes"][0]

    story = {
        "group_name": summary.get("group_name", ""),
        "date": date_label,
        "time_range": summary.get("time_range") or analysis.get("date_range", {}).get("label", ""),
        "lead_title": lead_title,
        "opening": opening,
        "timeline": timeline,
        "highlights": highlights,
        "sops": preset.get("sops", []),
        "qas": preset.get("qas", []),
        "stats": {
            "total_messages": analysis.get("total_messages", 0),
            "unique_senders": analysis.get("active_senders", 0),
            "total_chars": char_count,
            "new_members": 0,
        },
        "footer_quote": {
            "text": footer_quote["text"] if footer_quote else summary.get("week_in_one_line", ""),
            "attr": (footer_quote["who"] if footer_quote else summary.get("group_name", "")) + f" · {date_label}",
        },
    }
    return story


def day_stats_items(summary: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, str]]:
    keyword_hits = analysis.get("keyword_hits", [])
    peak_day = analysis.get("peak_day", {})
    top_sender = analysis.get("top_senders", [{}])[0]
    items = [
        {"n": str(analysis.get("total_messages", 0)), "l": "Messages"},
        {"n": str(analysis.get("active_senders", 0)), "l": "People"},
        {"n": str(analysis.get("char_count", 0)), "l": "Chars"},
        {"n": str(peak_day.get("count", 0)), "l": "Peak Day"},
        {"n": str(top_sender.get("count", 0)), "l": (top_sender.get("name", "Top") or "Top")[:8]},
    ]
    if keyword_hits:
        items.append({"n": str(keyword_hits[0].get("count", 0)), "l": keyword_hits[0].get("keyword", "Hot")[:8]})
    if len(summary.get("main_threads", [])) >= 1:
        items.append({"n": str(len(summary["main_threads"])), "l": "Threads"})
    items.append({"n": str(len(summary.get("links", []))), "l": "Links"})
    return items[:8]


def daily_strip_items(analysis: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for day in analysis.get("daily_breakdown", [])[:6]:
        top_sender = day.get("top_senders", [{}])[0]
        date = day.get("date", "")
        label = date[5:] if len(date) >= 10 else date
        items.append(
            {
                "time": label,
                "text": f"{day.get('total', 0)} 条消息，主讲位是 {top_sender.get('name', '群成员')}",
                "who": f"— {top_sender.get('count', 0)} 条 / char {day.get('char_count', 0)}",
            }
        )
    while len(items) < 6:
        items.append({"time": "--", "text": "本周节奏在这里留白。", "who": "— Weekly pacing"})
    return items


def quote_wall_items(quote_pool: list[dict[str, str]], n: int = 8) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not quote_pool:
        return [{"t": "本周继续施工。", "cite": "群聊现场"} for _ in range(n)]
    for idx in range(n):
        q = quote_pool[idx % len(quote_pool)]
        items.append({"t": q["text"], "cite": q["cite"]})
    return items


def letters_items(quote_pool: list[dict[str, str]], start: int = 0) -> list[dict[str, str]]:
    if not quote_pool:
        return [{"text": "本周群聊仍在继续。", "from": "— Weekly Notes"}] * 3
    out = []
    for idx in range(3):
        q = quote_pool[(start + idx) % len(quote_pool)]
        out.append({"text": q["text"], "from": f"— {q['cite']}"})
    return out


def keyword_lingo_items(analysis: dict[str, Any], n: int = 6) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for hit in analysis.get("keyword_hits", [])[:n]:
        items.append(
            {
                "w": hit["keyword"],
                "d": f"本周在群聊里出现 {hit['count']} 次，代表这一轮共同关注的操作面。",
            }
        )
    while len(items) < n:
        items.append({"w": "Workflow", "d": "本周群聊仍在围着真实使用与现场排障转。"})
    return items


def produced_list_from_links(summary: dict[str, Any], start: int = 0) -> list[dict[str, str]]:
    links = summary.get("links", [])
    out = []
    for idx, link in enumerate(links[start : start + 3], start=1):
        out.append(
            {
                "no": f"{idx:02d}",
                "title": link["title"][:28],
                "desc": link.get("note", "")[:80],
            }
        )
    while len(out) < 3:
        out.append({"no": f"{len(out)+1:02d}", "title": "本周产出待补", "desc": "这一格留给下一轮稳定 SOP。"})
    return out


def infer_total_pages(summary: dict[str, Any], analysis: dict[str, Any]) -> int:
    if analysis.get("total_messages", 0) >= 1000 or len(summary.get("main_threads", [])) >= 6:
        return 6
    return 4


def headline_from_thread(thread: dict[str, Any], summary: dict[str, Any]) -> str:
    subtitle = summary.get("subheadline") or summary.get("week_in_one_line") or ""
    return f"{thread['title']}<br><span class=\"deck\">{html.escape(subtitle)}</span>"


def build_layout(
    summary: dict[str, Any],
    analysis: dict[str, Any],
    story: dict[str, Any],
    preset: dict[str, Any],
    images_rel: dict[str, str],
) -> dict[str, Any]:
    people = summary.get("people", [])
    threads = summary.get("main_threads", [])
    quote_pool = build_quote_pool(summary, analysis)
    total_pages = infer_total_pages(summary, analysis)
    until = analysis.get("date_range", {}).get("until", "")
    mmdd = until[5:].replace("-", "") if len(until) >= 10 else "WEEK"
    group_name = summary.get("group_name", "")
    masthead = {
        "name_top": short_group_name(group_name),
        "name_bot": "周报",
        "pinyin": f"{short_group_name(group_name).upper()} · WEEKLY",
        "slogan_en": "A NEWSPAPER FOR ONE WECHAT GROUP",
        "slogan_cn_html": "群 聊 · 折 腾 · 共 建<br>把 一 周 对 话 变 成 可 读 的 工 作 档 案",
        "promo_tag": "Legacy Newspaper Renderer · Weekly Edition",
        "lunar": "本周合刊",
        "publisher": f"{group_name}群出版",
        "cn_no": f"CN 11-{mmdd}",
        "issue_code": f"代号 {mmdd}",
        "issue_no": f"第 {mmdd} 期",
        "total_pages": f"本周 {total_pages} 版",
        "footer_brand": f"{short_group_name(group_name)} · WEEKLY",
    }
    masthead.update(preset.get("masthead", {}))

    keyword_hits = analysis.get("keyword_hits", [])
    top_keyword = keyword_hits[0].get("keyword", "Weekly") if len(keyword_hits) > 0 else "Weekly"
    top_keyword2 = keyword_hits[1].get("keyword", "Report") if len(keyword_hits) > 1 else "Report"
    top_keyword3 = keyword_hits[2].get("keyword", "Flow") if len(keyword_hits) > 2 else "Flow"
    badge = f"{top_keyword} / {top_keyword2} / {top_keyword3}"

    page2_person = choose_person(people, preset.get("page2_person"), 0)
    page5_person = choose_person(people, preset.get("page5_person"), 1)

    day_items = daily_strip_items(analysis)
    quote_wall = quote_wall_items(quote_pool)
    letters = letters_items(quote_pool, 2)
    letters2 = letters_items(quote_pool, 5)
    lingo = keyword_lingo_items(analysis)

    def safe_title(idx: int, fallback: str) -> str:
        return threads[idx]["title"] if idx < len(threads) else fallback

    page1_indices = [0]
    if len(threads) > 1:
        page1_indices.append(1)
    page2_indices = [2] if len(threads) > 2 else [0]
    page3_indices = [3] if len(threads) > 3 else [len(threads) - 1]
    page5_indices = [4] if len(threads) > 4 else [page3_indices[0]]
    page6_indices = [5] if len(threads) > 5 else [page5_indices[0]]

    layout = {
        "masthead": masthead,
        "page1": {
            "template": "masthead",
            "name": "头 版 要 闻",
            "foot": f"第 1 版 / 共 {total_pages} 版 · 头 版 要 闻",
            "lead_kicker": f"一 周 群 聊 观 测 · {short_group_name(group_name)} · WEEKLY NOTEBOOK",
            "hero": {
                "eyebrow": "WEEKLY FRONT PAGE · EXCLUSIVE REPORT",
                "title_html": headline_from_thread(threads[0], summary) if threads else html.escape(summary.get("headline", "群聊周报")),
                "time": summary.get("time_range", ""),
                "badge": badge,
                "timeline_indices": page1_indices,
                "story_break_html": "▼ 本周另一条主线 ▼" if len(page1_indices) > 1 else "",
                "quotes_pick": [[idx, 0] for idx in page1_indices],
                "produced_html": "<b>PRODUCED ·</b> " + "；".join(link["title"][:22] for link in summary.get("links", [])[:3]),
            },
            "aside": {
                "figure": {
                    "image": images_rel["cover"],
                    "alt": f"{group_name} weekly cover",
                    "eyebrow": "本 周 封 面 · COVER NOTE",
                    "text": summary.get("opening", "")[:180],
                    "credit": f"— {summary.get('time_range','')} / Weekly cover card",
                },
                "side_banner": "本 周 花 絮 · SIDE NOTES",
                "briefings": [
                    {
                        "time": item["time"],
                        "title": item["text"][:16],
                        "desc": item["who"].replace("— ", ""),
                    }
                    for item in day_items[:3]
                ],
                "side_quote": {
                    "text_html": html.escape((summary.get("week_in_one_line") or summary.get("headline") or "本周继续施工。")[:18]),
                    "attr": f"— {group_name} · weekly line",
                },
            },
            "photo_strip": {
                "banner": f"本 周 合 影 · {short_group_name(group_name)} 8 位高频登场成员",
                "caption": f"{summary.get('time_range','')} · {group_name} 一周主要参演阵容",
            },
            "day_stats": {
                "banner": f"本 周 数 字 · BY THE NUMBERS · {short_group_name(group_name)} 7 天观测",
                "items": day_stats_items(summary, analysis),
            },
        },
        "page2": {
            "template": "communal",
            "name": preset.get("page2_name", "共 建 · 主 题 版"),
            "foot": f"第 2 版 / 共 {total_pages} 版 · {preset.get('page2_name', '共 建 · 主 题 版')}",
            "theme_title_html": f"{html.escape(page2_person['name'])}<br><span class=\"pbt-deck\">{html.escape(page2_person.get('desc',''))}</span>",
            "theme_en": "KEY PERSON · WEEKLY NODE",
            "person_card": {
                "image": images_rel["person1"],
                "alt": page2_person["name"],
                "eyebrow": "本 版 关 键 人 物 · KEY PERSON",
                "quote_block_title": f"{page2_person['name']} · 本周速写",
                "quote_block_lines": [
                    [summary.get("timeline", [])[0]["date"].split("-")[-1] if summary.get("timeline") else "--", page2_person.get("tag", "活跃成员")],
                    ["角色", page2_person.get("desc", "")[:26]],
                    ["定位", page2_person["name"]],
                ],
                "caption_html": f"<b>图：</b>{html.escape(page2_person.get('desc',''))}",
            },
            "hero": {
                "eyebrow": "本 版 头 条 · WEEKLY SECTION",
                "title_html": headline_from_thread(threads[page2_indices[0]], summary) if threads else html.escape(summary.get("headline", "")),
                "time": summary.get("time_range", ""),
                "badge": badge,
                "timeline_indices": page2_indices,
                "story_break_html": "",
                "quotes_pick": [[page2_indices[0], 0]],
                "produced_html": "<b>PRODUCED ·</b> " + "；".join(item["title"] for item in produced_list_from_links(summary, 0)),
            },
            "produced_list": {
                "banner": "本 周 产 出 物 · PRODUCED TODAY",
                "items": produced_list_from_links(summary, 0),
            },
            "timeline_strip": {
                "banner": "一 周 节 奏 · 6 个 关 键 日",
                "items": day_items,
            },
            "quote_wall": {
                "banner": "群 成 员 当 周 金 句 · TODAY'S VOICES",
                "items": quote_wall,
            },
        },
        "page3": {
            "template": "feature",
            "name": preset.get("page3_name", "副 刊 · 深 度 版"),
            "foot": f"第 3 版 / 共 {total_pages} 版 · {preset.get('page3_name', '副 刊 · 深 度 版')}",
            "theme_title_html": f"{html.escape(safe_title(page3_indices[0], '本周副刊'))}<br><span class=\"pbt-deck\">{html.escape(summary.get('subheadline',''))}</span>",
            "theme_en": "FEATURE · WEEKLY WORKFLOW",
            "banner_image": {
                "image": images_rel["workflow"],
                "alt": "weekly workflow map",
                "eyebrow": "本 版 镇 版 图 · COVER IMAGE",
                "title": safe_title(page3_indices[0], "本周副刊"),
                "text": threads[page3_indices[0]]["summary"][:180] if threads else summary.get("opening", "")[:180],
                "credit": f"— {short_group_name(group_name)} / workflow map",
            },
            "hero": {
                "eyebrow": "本 版 头 条 · FEATURE REPORT",
                "title_html": headline_from_thread(threads[page3_indices[0]], summary) if threads else html.escape(summary.get("headline", "")),
                "time": summary.get("time_range", ""),
                "badge": badge,
                "timeline_indices": page3_indices,
                "story_break_html": "",
                "quotes_pick": [[page3_indices[0], 0]],
                "produced_html": "<b>PRODUCED ·</b> " + "；".join(item["title"] for item in produced_list_from_links(summary, 1)),
            },
            "timeline_strip": {
                "banner": "本 周 线 索 · DAILY STRIP",
                "items": day_items,
            },
            "letters": {
                "banner": "群 友 回 声 · LETTERS",
                "items": letters,
            },
            "lingo": {
                "banner": "本 周 热 词 · WEEKLY LINGO",
                "items": lingo,
            },
        },
        "page4": {
            "template": "cast",
            "name": "人 物 · 高 光 · 附 录",
            "foot": f"第 4 版 / 共 {total_pages} 版 · 人 物 · 高 光 · 附 录",
            "theme_title_html": "本 周 高 光 · 让 这 一 周 立 住 的 8 个 人",
            "theme_en": "WEEKLY CAST · EIGHT PEOPLE WHO MADE THE WEEK",
            "appendix_banner": "附 录 · APPENDIX · 可 抄 作 业 · BRING YOUR OWN WORKFLOW",
            "sop_title": "可 抄 作 业 · 实 操 SOP",
            "qa_title": "群 友 答 疑 · Q & A",
            "tomorrow": {
                "banner": "下 回 分 解 · COMING NEXT · 这 群 接 下 来 还 会 干 什 么",
                "items": [
                    {
                        "tag": f"{idx+1:02d}",
                        "title": item[:18],
                        "desc": item,
                    }
                    for idx, item in enumerate(summary.get("next_actions", [])[:4])
                ]
                or [
                    {"tag": "NEXT", "title": "继续施工", "desc": "这份报纸链路已经恢复，下一步适合沉淀成稳定 skill。"}
                ],
                "qr": {
                    "image": images_rel["deploy"],
                    "alt": "Self-hosted deploy card",
                    "title_html": "Self-Hosted Ready<br>Weekly Archive",
                    "desc": "本页保留给部署与分享；重跑后可替换为正式访问地址或自定义域名。",
                },
            },
        },
    }

    if total_pages >= 6:
        layout["page5"] = {
            "template": "communal",
            "name": preset.get("page5_name", "共 建 · 二 号 主 题"),
            "foot": f"第 5 版 / 共 {total_pages} 版 · {preset.get('page5_name', '共 建 · 二 号 主 题')}",
            "theme_title_html": f"{html.escape(page5_person['name'])}<br><span class=\"pbt-deck\">{html.escape(page5_person.get('desc',''))}</span>",
            "theme_en": "SECOND NODE · BUILDER DIARY",
            "person_card": {
                "image": images_rel["person2"],
                "alt": page5_person["name"],
                "eyebrow": "本 版 关 键 人 物 · KEY PERSON",
                "quote_block_title": f"{page5_person['name']} · 本周侧写",
                "quote_block_lines": [
                    ["身份", page5_person.get("tag", "活跃成员")],
                    ["特点", page5_person.get("desc", "")[:28]],
                    ["记录", page5_person["name"]],
                ],
                "caption_html": f"<b>图：</b>{html.escape(page5_person.get('desc',''))}",
            },
            "hero": {
                "eyebrow": "本 版 头 条 · BUILDER LOG",
                "title_html": headline_from_thread(threads[page5_indices[0]], summary) if threads else html.escape(summary.get("headline", "")),
                "time": summary.get("time_range", ""),
                "badge": badge,
                "timeline_indices": page5_indices,
                "story_break_html": "",
                "quotes_pick": [[page5_indices[0], 0]],
                "produced_html": "<b>PRODUCED ·</b> " + "；".join(item["title"] for item in produced_list_from_links(summary, 2)),
            },
            "produced_list": {
                "banner": "本 周 续 集 · WHAT KEPT MOVING",
                "items": produced_list_from_links(summary, 2),
            },
            "timeline_strip": {
                "banner": "延 伸 节 点 · 6 个 续 集",
                "items": day_items,
            },
            "quote_wall": {
                "banner": "本 周 第二组金句 · SECOND WALL",
                "items": quote_wall_items(quote_pool[3:] + quote_pool[:3], 8),
            },
        }
        layout["page6"] = {
            "template": "feature",
            "name": preset.get("page6_name", "尾 版 · 群 文 化"),
            "foot": f"第 6 版 / 共 {total_pages} 版 · {preset.get('page6_name', '尾 版 · 群 文 化')}",
            "theme_title_html": f"{html.escape(safe_title(page6_indices[0], '尾版主题'))}<br><span class=\"pbt-deck\">{html.escape(summary.get('week_in_one_line',''))}</span>",
            "theme_en": "CULTURE ARCHIVE · WEEKLY ENDNOTE",
            "banner_image": {
                "image": images_rel["culture"],
                "alt": "culture archive",
                "eyebrow": "本 版 镇 版 图 · COVER IMAGE",
                "title": safe_title(page6_indices[0], "尾版主题"),
                "text": threads[page6_indices[0]]["summary"][:180] if threads else summary.get("opening", "")[:180],
                "credit": f"— {short_group_name(group_name)} / culture board",
            },
            "hero": {
                "eyebrow": "尾 版 主 稿 · FINAL FEATURE",
                "title_html": headline_from_thread(threads[page6_indices[0]], summary) if threads else html.escape(summary.get("headline", "")),
                "time": summary.get("time_range", ""),
                "badge": badge,
                "timeline_indices": page6_indices,
                "story_break_html": "",
                "quotes_pick": [[page6_indices[0], 0]],
                "produced_html": "<b>PRODUCED ·</b> " + "；".join(item["title"] for item in produced_list_from_links(summary, 3)),
            },
            "timeline_strip": {
                "banner": "尾 版 节 奏 · WEEKEND STRIP",
                "items": day_items,
            },
            "letters": {
                "banner": "群 友 余 音 · LETTERS",
                "items": letters2,
            },
            "lingo": {
                "banner": "本 周 余 温 · CLOSING LINGO",
                "items": lingo,
            },
        }

    return layout


def draw_cover(path: Path, group_name: str, time_range: str, headline: str, subtitle: str, threads: list[dict[str, Any]], accent: str, dark: str) -> None:
    img, draw = make_canvas(1080, 1480, "#f6f0e6")
    draw.rectangle([0, 0, 1080, 220], fill=accent)
    draw.rectangle([60, 260, 1020, 1420], outline=dark, width=4)
    title_font = font("serif", 74)
    sub_font = font("sans", 28)
    body_font = font("serif", 36)
    small_font = font("sans", 22)
    draw.text((72, 58), short_group_name(group_name), font=title_font, fill="#fffdf8")
    draw.text((78, 162), time_range, font=sub_font, fill="#f6f0e6")
    y = draw_multiline(draw, (92, 320, 980, 700), headline, font("serif", 60), dark, 14)
    draw_multiline(draw, (92, y + 28, 980, 860), subtitle, font("serif", 26), "#3e342d", 10)
    y = 920
    draw.text((92, y), "本 周 版 面 线 索", font=font("sans", 28), fill=accent)
    y += 56
    for idx, thread in enumerate(threads[:4], start=1):
        draw.text((102, y), f"{idx:02d}", font=font("latin", 34), fill=accent)
        draw_multiline(draw, (162, y - 6, 960, y + 90), thread["title"], body_font, dark, 8)
        y += 120
    draw.text((92, 1360), "Legacy newspaper path restored", font=small_font, fill="#6d6258")
    draw.text((92, 1392), "summary -> story/layout -> render_newspaper.py -> publisher", font=small_font, fill="#6d6258")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def draw_person_card(path: Path, person: dict[str, Any], quote: str, accent: str, dark: str, reverse: bool = False) -> None:
    bg = dark if not reverse else "#f5efe6"
    fg = "#f6efe5" if not reverse else dark
    img, draw = make_canvas(900, 1280, bg)
    draw.rectangle([48, 48, 852, 1232], outline=accent if reverse else "#c8b7a4", width=3)
    draw.text((86, 92), "KEY PERSON", font=font("sans", 30), fill=accent if reverse else "#d2c0ab")
    name_font = font("serif", 68)
    draw_multiline(draw, (86, 170, 810, 420), person["name"], name_font, fg, 10)
    draw.text((86, 432), person.get("tag", ""), font=font("sans", 24), fill=accent if reverse else "#c8b7a4")
    draw.rectangle([86, 500, 810, 820], fill=accent if reverse else "#f6efe5")
    draw_multiline(draw, (118, 548, 778, 788), person.get("desc", ""), font("serif", 30), "#f6efe5" if reverse else dark, 10)
    draw.text((86, 890), "WEEKLY NOTE", font=font("sans", 24), fill=accent if reverse else "#d2c0ab")
    draw_multiline(draw, (86, 942, 812, 1170), f"“{quote}”", font("serif", 34), fg, 12)
    img.save(path)


def draw_workflow(path: Path, group_name: str, threads: list[dict[str, Any]], accent: str, dark: str) -> None:
    img, draw = make_canvas(1600, 880, "#f7f2ea")
    draw.rectangle([0, 0, 1600, 120], fill=accent)
    draw.text((58, 34), f"{short_group_name(group_name)} · WORKFLOW MAP", font=font("sans", 38), fill="#fffdf8")
    box_font = font("serif", 34)
    desc_font = font("sans", 22)
    coords = [
        (70, 200, 500, 420),
        (550, 200, 980, 420),
        (1090, 200, 1520, 420),
        (310, 500, 740, 720),
        (860, 500, 1290, 720),
    ]
    use_threads = threads[:5] or [{"title": "本周主线", "summary": "群聊仍在施工。"}]
    while len(use_threads) < len(coords):
        use_threads.append(use_threads[-1])
    for idx, (x1, y1, x2, y2) in enumerate(coords):
        draw.rounded_rectangle([x1, y1, x2, y2], radius=24, outline=dark, width=3, fill="#fffdfa")
        draw.text((x1 + 22, y1 + 20), f"{idx+1:02d}", font=font("latin", 30), fill=accent)
        draw_multiline(draw, (x1 + 22, y1 + 64, x2 - 22, y1 + 150), use_threads[idx]["title"], box_font, dark, 8)
        draw_multiline(draw, (x1 + 22, y1 + 154, x2 - 22, y2 - 24), use_threads[idx]["summary"][:90], desc_font, "#3f372f", 6)
    for (sx1, sy1, sx2, sy2), (tx1, ty1, tx2, ty2) in zip(coords[:-1], coords[1:]):
        x_start = sx2
        y_start = (sy1 + sy2) // 2
        x_end = tx1
        y_end = (ty1 + ty2) // 2
        draw.line([x_start, y_start, x_end, y_end], fill=accent, width=5)
        draw.polygon([(x_end, y_end), (x_end - 16, y_end - 10), (x_end - 16, y_end + 10)], fill=accent)
    img.save(path)


def draw_deploy(path: Path, group_name: str, accent: str, dark: str) -> None:
    img, draw = make_canvas(880, 880, "#fbf7ef")
    draw.rectangle([0, 0, 880, 120], fill=dark)
    draw.text((48, 34), "SELF HOST READY", font=font("sans", 42), fill="#fbf7ef")
    fake_qr(draw, (120, 180, 760, 760), f"{group_name}-publisher")
    draw.text((160, 782), short_group_name(group_name), font=font("serif", 40), fill=accent)
    draw.text((160, 830), "weekly archive slot", font=font("sans", 24), fill="#5e554d")
    img.save(path)


def draw_culture(path: Path, group_name: str, keywords: list[dict[str, Any]], daily: list[dict[str, Any]], accent: str, dark: str) -> None:
    img, draw = make_canvas(1600, 900, "#f5efe7")
    draw.rectangle([0, 0, 1600, 140], fill=accent)
    draw.text((60, 42), f"{short_group_name(group_name)} · CULTURE BOARD", font=font("sans", 42), fill="#fffdf8")
    y = 210
    chip_font = font("sans", 28)
    for idx, hit in enumerate(keywords[:6]):
        x = 70 + (idx % 3) * 500
        yy = y + (idx // 3) * 150
        draw.rounded_rectangle([x, yy, x + 420, yy + 92], radius=18, outline=dark, width=2, fill="#fffaf3")
        draw.text((x + 24, yy + 18), hit["keyword"], font=chip_font, fill=accent)
        draw.text((x + 250, yy + 24), f"{hit['count']} 次", font=font("sans", 22), fill=dark)
    y2 = 560
    draw.text((70, y2), "一 周 节 奏", font=font("sans", 30), fill=dark)
    for idx, day in enumerate(daily[:4]):
        yy = y2 + 60 + idx * 62
        draw.line([70, yy + 18, 1530, yy + 18], fill="#cfc2b3", width=1)
        draw.text((80, yy), day["time"], font=font("latin", 26), fill=accent)
        draw.text((220, yy), day["text"][:42], font=font("serif", 28), fill=dark)
    img.save(path)


def ensure_images(
    image_dir: Path,
    summary: dict[str, Any],
    analysis: dict[str, Any],
    preset: dict[str, Any],
) -> dict[str, str]:
    image_dir.mkdir(parents=True, exist_ok=True)
    accent = preset.get("accent", "#8f2f25")
    dark = preset.get("dark", "#1f1915")
    group_name = summary.get("group_name", "")
    threads = summary.get("main_threads", [])
    people = summary.get("people", [])
    quote_pool = build_quote_pool(summary, analysis)
    person1 = choose_person(people, preset.get("page2_person"), 0)
    person2 = choose_person(people, preset.get("page5_person"), 1)
    q1 = quote_pool[0]["text"] if quote_pool else summary.get("headline", "")
    q2 = quote_pool[1]["text"] if len(quote_pool) > 1 else summary.get("week_in_one_line", "")

    cover = image_dir / "cover-front.png"
    person_card1 = image_dir / "person-card-1.png"
    workflow = image_dir / "workflow-map.png"
    deploy = image_dir / "deploy-card.png"
    person_card2 = image_dir / "person-card-2.png"
    culture = image_dir / "culture-paper.png"

    draw_cover(
        cover,
        group_name,
        summary.get("time_range", ""),
        summary.get("headline", "群聊周报"),
        summary.get("subheadline", ""),
        threads,
        accent,
        dark,
    )
    draw_person_card(person_card1, person1, q1, accent, dark, reverse=False)
    draw_workflow(workflow, group_name, threads, accent, dark)
    draw_deploy(deploy, group_name, accent, dark)
    draw_person_card(person_card2, person2, q2, accent, dark, reverse=True)
    draw_culture(culture, group_name, analysis.get("keyword_hits", []), daily_strip_items(analysis), accent, dark)

    return {
        "cover": "images/cover-front.png",
        "person1": "images/person-card-1.png",
        "workflow": "images/workflow-map.png",
        "deploy": "images/deploy-card.png",
        "person2": "images/person-card-2.png",
        "culture": "images/culture-paper.png",
    }


def patch_fixed_height(html_path: Path) -> None:
    text = html_path.read_text(encoding="utf-8")
    text = text.replace("min-height: 1587px;", "height: 1587px; overflow: hidden;")
    html_path.write_text(text, encoding="utf-8")


def print_pdf(html_path: Path, pdf_path: Path, expected_pages: int) -> int:
    if not CHROME.exists() or not PDFINFO:
        return 0
    cmd = [
        str(CHROME),
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        f"--user-data-dir=/tmp/chrome-pdf-{os_hash(str(pdf_path))}",
        "--virtual-time-budget=20000",
        "--hide-scrollbars",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        html_path.as_uri(),
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    last_size = -1
    stable_hits = 0
    deadline = time.time() + 60
    while time.time() < deadline:
        if pdf_path.exists():
            size = pdf_path.stat().st_size
            if size > 0 and size == last_size:
                stable_hits += 1
            else:
                stable_hits = 0
                last_size = size
            if stable_hits >= 2:
                break
        if proc.poll() is not None and pdf_path.exists():
            break
        time.sleep(1)
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    if not pdf_path.exists():
        raise RuntimeError(f"PDF was not generated: {pdf_path}")
    proc = subprocess.run(
        [PDFINFO, str(pdf_path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    pages = 0
    for line in proc.stdout.splitlines():
        if line.startswith("Pages:"):
            pages = int(line.split(":", 1)[1].strip())
            break
    if pages != expected_pages:
        raise RuntimeError(f"Expected {expected_pages} PDF pages, got {pages}")
    return pages


def os_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def build_avatars_file(group_dir: Path, out_path: Path) -> None:
    source = group_dir / "newspaper" / "avatars.json"
    if source.exists():
        shutil.copy2(source, out_path)
        return
    out_path.write_text("{}", encoding="utf-8")


def copy_site_to_dist(site_dir: Path, dist_dir: Path) -> None:
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    shutil.copytree(site_dir, dist_dir)


def build_render_payload(
    summary: dict[str, Any],
    analysis: dict[str, Any],
    group_dir: Path,
    run_dir: Path,
) -> dict[str, Any]:
    preset = pick_preset(summary, analysis)
    site_dir = run_dir / "site"
    dist_dir = run_dir / "dist"
    images_dir = site_dir / "images"
    site_dir.mkdir(parents=True, exist_ok=True)

    images_rel = ensure_images(images_dir, summary, analysis, preset)
    avatars_path = run_dir / "avatars.json"
    build_avatars_file(group_dir, avatars_path)
    story = build_story(summary, analysis, preset)
    layout = build_layout(summary, analysis, story, preset, images_rel)
    html_text = render_newspaper_html(story, load_json(avatars_path), layout)

    story_path = run_dir / "story.json"
    layout_path = run_dir / "layout-plan.json"
    html_path = site_dir / "index.html"
    pdf_path = run_dir / "newspaper.pdf"

    save_json(story_path, story)
    save_json(layout_path, layout)
    html_path.write_text(html_text, encoding="utf-8")
    patch_fixed_height(html_path)
    head_markup = build_branding_head(group_dir, site_dir)
    if head_markup:
        html_path.write_text(
            inject_branding_head(html_path.read_text(encoding="utf-8"), head_markup),
            encoding="utf-8",
        )
    copy_site_to_dist(site_dir, dist_dir)

    return {
        "story": story,
        "layout": layout,
        "html": html_path.read_text(encoding="utf-8"),
        "story_json": str(story_path),
        "layout_plan_json": str(layout_path),
        "avatars_json": str(avatars_path),
        "site_index": str(html_path),
        "dist_index": str(dist_dir / "index.html"),
        "pdf": str(pdf_path),
    }


def render_html(summary: dict[str, Any], analysis: dict[str, Any]) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        group_dir = tmp_root / "group"
        run_dir = group_dir / "newspaper" / "preview"
        group_dir.mkdir(parents=True, exist_ok=True)
        return build_render_payload(summary, analysis, group_dir, run_dir)["html"]


def render(summary_path: Path, analysis_path: Path) -> dict[str, Any]:
    summary = load_json(summary_path)
    analysis = load_json(analysis_path)

    group_dir = summary_path.parent.parent
    range_slug = f"{analysis['date_range']['since']}_{analysis['date_range']['until']}"
    newspaper_run_dir = group_dir / "newspaper" / range_slug
    result = build_render_payload(summary, analysis, group_dir, newspaper_run_dir)
    site_dir = newspaper_run_dir / "site"
    dist_dir = newspaper_run_dir / "dist"
    pdf_path = Path(result["pdf"])

    # Promote latest newspaper to the group root site/dist so the existing paths keep working.
    promoted_site = group_dir / "site"
    promoted_dist = group_dir / "dist"
    if promoted_site.exists():
        shutil.rmtree(promoted_site)
    shutil.copytree(site_dir, promoted_site)
    if promoted_dist.exists():
        shutil.rmtree(promoted_dist)
    shutil.copytree(dist_dir, promoted_dist)

    latest_newspaper_dir = group_dir / "newspaper"
    latest_newspaper_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(result["story_json"], latest_newspaper_dir / "story.json")
    shutil.copy2(result["layout_plan_json"], latest_newspaper_dir / "layout-plan.json")
    shutil.copy2(result["avatars_json"], latest_newspaper_dir / "avatars.json")

    pages = infer_total_pages(summary, analysis)
    rendered_pages = print_pdf(site_dir / "index.html", pdf_path, pages)

    return {
        "group_dir": str(group_dir),
        "range_dir": str(newspaper_run_dir),
        "story_json": result["story_json"],
        "layout_plan_json": result["layout_plan_json"],
        "site_index": result["site_index"],
        "dist_index": result["dist_index"],
        "pdf": str(pdf_path),
        "pdf_pages": rendered_pages,
        "promoted_site_index": str(promoted_site / "index.html"),
        "promoted_dist_index": str(promoted_dist / "index.html"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Render summary into the newspaper webpage pipeline")
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--analysis", required=True, type=Path)
    args = parser.parse_args()
    result = render(args.summary.resolve(), args.analysis.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
