#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_KEYWORDS = [
    "Codex",
    "Claude",
    "Claude Code",
    "ChatGPT",
    "OpenAI",
    "Gemini",
    "Flow",
    "Veo",
    "Nano Banana",
    "Skill",
    "Skills",
    "Cursor",
    "Trae",
    "Kimi",
    "Obsidian",
    "PPT",
    "GitHub",
    "API",
    "token",
    "deploy",
    "Humanizer",
    "AIGC",
    "知识库",
    "公众号",
    "生图",
]


QUOTE_RE = re.compile(r"^\[引用\]\s*(.*?)\n\s*↳\s*([^:]+):\s*(.*)$", re.S)
LINK_RE = re.compile(r"^\[(链接|文件)\]\s*(.+)$")


@dataclass
class Message:
    local_id: Any
    sender: str
    time: str
    timestamp: int
    type: str
    content: str

    @property
    def date(self) -> str:
        return self.time[:10]

    @property
    def hour(self) -> int:
        return int(self.time[11:13])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a WeChat summary analysis bundle.")
    parser.add_argument("--chat", required=True, help="Exact chat name for wx-cli.")
    parser.add_argument("--since", required=True, help="Start date YYYY-MM-DD.")
    parser.add_argument("--until", required=True, help="End date YYYY-MM-DD.")
    parser.add_argument(
        "--data-root",
        default="wechat",
        help="Where group folders should be created. Default: ./wechat",
    )
    parser.add_argument("--limit", type=int, default=5000, help="wx history fetch cap.")
    return parser.parse_args()


def run_json(cmd: list[str]) -> Any:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def sanitize_group_name(name: str) -> str:
    sanitized = re.sub(r'[\/\\:\*\?"<>\|\x00-\x1f]', "_", name).rstrip(". ").strip()
    return sanitized or "unnamed-group"


def normalize_messages(payload: list[dict[str, Any]]) -> list[Message]:
    messages: list[Message] = []
    for item in payload:
        messages.append(
            Message(
                local_id=item.get("local_id") or item.get("id") or item.get("msg_id"),
                sender=(item.get("sender") or "").strip(),
                time=item.get("time") or "",
                timestamp=int(item.get("timestamp") or 0),
                type=item.get("type") or "未知",
                content=(item.get("content") or "").strip(),
            )
        )
    return messages


def link_title(content: str) -> str | None:
    match = LINK_RE.match(content)
    if not match:
        return None
    title = match.group(2).strip()
    if not title:
        return None
    if " tickled " in title:
        return None
    return title[:200]


def parse_quote(content: str) -> dict[str, str] | None:
    match = QUOTE_RE.match(content)
    if not match:
        return None
    return {
        "quoted_preview": match.group(1).strip()[:120],
        "quoted_sender": match.group(2).strip(),
        "reply_preview": match.group(3).strip()[:180],
    }


def char_count(msg: Message) -> int:
    if msg.type != "文本":
        return 0
    return len(msg.content)


def should_count_sender(msg: Message) -> bool:
    return bool(msg.sender) and msg.type != "系统"


def quote_score(msg: Message) -> int:
    if not should_count_sender(msg):
        return -999
    content = msg.content
    score = 0
    if msg.type == "文本":
        score += 3
    if content.startswith("[引用]"):
        score += 6
    if 12 <= len(content) <= 140:
        score += 3
    if "http" in content or "https" in content:
        score += 1
    if any(token.lower() in content.lower() for token in ["为什么", "可以", "不行", "应该", "问题", "好用"]):
        score += 2
    if content.startswith("[表情]") or content.startswith("[图片]") or content.startswith("[视频]"):
        score -= 5
    return score


def top_quote_candidates(messages: list[Message], limit: int = 30) -> list[dict[str, Any]]:
    ranked = sorted(messages, key=lambda msg: (quote_score(msg), msg.timestamp), reverse=True)
    seen: set[tuple[str, str]] = set()
    picks: list[dict[str, Any]] = []
    for msg in ranked:
        if len(picks) >= limit:
            break
        if quote_score(msg) < 4:
            break
        key = (msg.sender, msg.content)
        if key in seen:
            continue
        seen.add(key)
        item = {
            "time": msg.time,
            "sender": msg.sender,
            "type": msg.type,
            "content": msg.content[:300],
        }
        quote = parse_quote(msg.content)
        if quote:
            item["quote_context"] = quote
        picks.append(item)
    return picks


def message_samples(messages: list[Message], per_day: int = 8) -> list[dict[str, Any]]:
    grouped: dict[str, list[Message]] = defaultdict(list)
    for msg in messages:
        grouped[msg.date].append(msg)

    samples: list[dict[str, Any]] = []
    for day in sorted(grouped):
        ranked = sorted(grouped[day], key=lambda msg: (quote_score(msg), msg.timestamp), reverse=True)
        picked = 0
        for msg in ranked:
            if picked >= per_day:
                break
            if not should_count_sender(msg):
                continue
            if msg.type not in {"文本", "链接/文件"}:
                continue
            if len(msg.content) < 6:
                continue
            samples.append(
                {
                    "time": msg.time,
                    "sender": msg.sender,
                    "type": msg.type,
                    "content": msg.content[:300],
                }
            )
            picked += 1
    return samples


def keyword_hits(messages: list[Message]) -> list[dict[str, Any]]:
    counts = Counter()
    for msg in messages:
        content = msg.content.lower()
        for keyword in TOOL_KEYWORDS:
            if keyword.lower() in content:
                counts[keyword] += 1
    return [{"keyword": key, "count": value} for key, value in counts.most_common(20)]


def build_analysis(messages: list[Message], stats: dict[str, Any], raw_file: Path) -> dict[str, Any]:
    participant_counts = Counter(msg.sender for msg in messages if should_count_sender(msg))
    by_type = Counter(msg.type for msg in messages)
    link_counts = Counter()
    daily_type_counts: dict[str, Counter[str]] = defaultdict(Counter)
    daily_sender_counts: dict[str, Counter[str]] = defaultdict(Counter)
    daily_totals = Counter()
    daily_chars = Counter()
    hour_counts = Counter()

    for msg in messages:
        daily_totals[msg.date] += 1
        daily_type_counts[msg.date][msg.type] += 1
        daily_chars[msg.date] += char_count(msg)
        hour_counts[msg.hour] += 1
        if should_count_sender(msg):
            daily_sender_counts[msg.date][msg.sender] += 1
        title = link_title(msg.content)
        if title:
            link_counts[title] += 1

    peak_day = daily_totals.most_common(1)[0] if daily_totals else ("", 0)
    peak_hour = hour_counts.most_common(1)[0] if hour_counts else (0, 0)
    first_message_time = messages[0].time if messages else ""
    last_message_time = messages[-1].time if messages else ""

    daily_breakdown = []
    for day in sorted(daily_totals):
        top_people = [
            {"name": name, "count": count}
            for name, count in daily_sender_counts[day].most_common(5)
        ]
        daily_breakdown.append(
            {
                "date": day,
                "total": daily_totals[day],
                "char_count": daily_chars[day],
                "by_type": dict(daily_type_counts[day]),
                "top_senders": top_people,
            }
        )

    return {
        "group_name": stats.get("chat"),
        "group_id": stats.get("username"),
        "date_range": {
            "since": args.since,
            "until": args.until,
            "label": f"{args.since} ~ {args.until}",
        },
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "total_messages": len(messages),
        "active_senders": len(participant_counts),
        "char_count": sum(char_count(msg) for msg in messages),
        "first_message_time": first_message_time,
        "last_message_time": last_message_time,
        "by_type": dict(by_type),
        "peak_day": {"date": peak_day[0], "count": peak_day[1]},
        "peak_hour": {"hour": peak_hour[0], "count": peak_hour[1]},
        "top_senders": [
            {"name": name, "count": count}
            for name, count in participant_counts.most_common(15)
        ],
        "daily_breakdown": daily_breakdown,
        "top_links": [
            {"title": title, "count": count}
            for title, count in link_counts.most_common(20)
        ],
        "keyword_hits": keyword_hits(messages),
        "quote_candidates": top_quote_candidates(messages),
        "message_samples": message_samples(messages),
        "raw_file": str(raw_file),
    }


def format_briefing(analysis: dict[str, Any]) -> str:
    lines = [
        f"# {analysis['group_name']} · Weekly Briefing",
        "",
        f"- Group ID: `{analysis['group_id']}`",
        f"- Range: `{analysis['date_range']['label']}`",
        f"- Total messages: `{analysis['total_messages']}`",
        f"- Active senders: `{analysis['active_senders']}`",
        f"- Total text chars: `{analysis['char_count']}`",
        f"- Peak day: `{analysis['peak_day']['date']}` ({analysis['peak_day']['count']} messages)",
        f"- Peak hour: `{analysis['peak_hour']['hour']:02d}:00` ({analysis['peak_hour']['count']} messages)",
        "",
        "## Top Senders",
        "",
    ]
    for item in analysis["top_senders"][:10]:
        lines.append(f"- {item['name']}: {item['count']}")

    lines.extend(["", "## Daily Breakdown", ""])
    for day in analysis["daily_breakdown"]:
        leaders = ", ".join(f"{item['name']} {item['count']}" for item in day["top_senders"][:3])
        lines.append(
            f"- {day['date']}: {day['total']} messages, {day['char_count']} chars, top senders: {leaders or 'n/a'}"
        )

    lines.extend(["", "## Tool / Topic Hints", ""])
    for item in analysis["keyword_hits"][:12]:
        lines.append(f"- {item['keyword']}: {item['count']}")

    lines.extend(["", "## Frequently Shared Links", ""])
    for item in analysis["top_links"][:12]:
        lines.append(f"- {item['title']} ({item['count']})")

    lines.extend(["", "## Quote Candidates", ""])
    for item in analysis["quote_candidates"][:20]:
        lines.append(f"- {item['time']} · {item['sender']}: {item['content']}")

    lines.extend(["", "## Message Samples", ""])
    for item in analysis["message_samples"][:30]:
        lines.append(f"- {item['time']} · {item['sender']}: {item['content']}")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    args = parse_args()

    history_payload = run_json(
        [
            "wx",
            "history",
            args.chat,
            "--since",
            args.since,
            "--until",
            args.until,
            "-n",
            str(args.limit),
            "--json",
        ]
    )
    stats_payload = run_json(
        [
            "wx",
            "stats",
            args.chat,
            "--since",
            args.since,
            "--until",
            args.until,
            "--json",
        ]
    )

    messages = normalize_messages(history_payload)
    group_name = stats_payload.get("chat") or args.chat
    group_id = stats_payload.get("username") or "unknown-group"
    group_dir = Path(args.data_root).expanduser().resolve() / f"{group_id}-{sanitize_group_name(group_name)}"
    raw_dir = group_dir / "raw"
    analysis_dir = group_dir / "analysis"
    raw_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    slug = f"{args.since}_{args.until}"
    raw_messages_file = raw_dir / f"{slug}.messages.json"
    raw_stats_file = raw_dir / f"{slug}.stats.json"
    analysis_file = analysis_dir / f"{slug}.analysis.json"
    briefing_file = analysis_dir / f"{slug}.briefing.md"

    raw_messages_file.write_text(
        json.dumps(history_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    raw_stats_file.write_text(
        json.dumps(stats_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    analysis = build_analysis(messages, stats_payload, raw_messages_file)
    analysis_file.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    briefing_file.write_text(format_briefing(analysis), encoding="utf-8")

    result = {
        "group_dir": str(group_dir),
        "analysis_json": str(analysis_file),
        "briefing_md": str(briefing_file),
        "raw_messages_json": str(raw_messages_file),
        "raw_stats_json": str(raw_stats_file),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
