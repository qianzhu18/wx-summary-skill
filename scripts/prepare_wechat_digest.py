#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
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
TIME_TOKEN_PATTERN = (
    r"(?:(?:上午|下午|晚上|中午|凌晨|早上)\s*)?\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?"
)
TIME_TOKEN_RE = re.compile(
    r"^(?P<prefix>上午|下午|晚上|中午|凌晨|早上)?\s*"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?"
    r"(?:\s*(?P<suffix>[AaPp][Mm]))?$"
)
HEADER_NAME_TIME_RE = re.compile(rf"^(?P<sender>.+?)\s+(?P<time>{TIME_TOKEN_PATTERN})$")
HEADER_TIME_NAME_RE = re.compile(rf"^(?P<time>{TIME_TOKEN_PATTERN})\s+(?P<sender>.+?)$")
FULL_DATE_RE = re.compile(
    r"^(?P<year>\d{4})[年/\-\.](?P<month>\d{1,2})[月/\-\.](?P<day>\d{1,2})日?"
    r"(?:\s*(?:星期|周)?[一二三四五六日天])?$"
)
PARTIAL_DATE_RE = re.compile(
    r"^(?P<month>\d{1,2})[月/\-\.](?P<day>\d{1,2})日?"
    r"(?:\s*(?:星期|周)?[一二三四五六日天])?$"
)
IGNORED_TRANSCRIPT_LINES = {
    "以下为新消息",
    "以下是新消息",
    "查看更多消息",
    "以上是打招呼的内容",
    "以下是打招呼的内容",
}


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
    parser.add_argument("--chat", required=True, help="Exact chat name or the manual transcript target chat name.")
    parser.add_argument("--since", required=True, help="Start date YYYY-MM-DD.")
    parser.add_argument("--until", required=True, help="End date YYYY-MM-DD.")
    parser.add_argument(
        "--data-root",
        default="wechat",
        help="Where group folders should be created. Default: ./wechat",
    )
    parser.add_argument("--limit", type=int, default=5000, help="wx history fetch cap.")
    parser.add_argument(
        "--source",
        choices=["wx-cli", "clipboard", "file", "stdin"],
        default="wx-cli",
        help="How to ingest chat data. Default: wx-cli.",
    )
    parser.add_argument(
        "--input-file",
        help="Plain-text transcript path for --source file.",
    )
    parser.add_argument(
        "--group-id",
        help="Optional group id override. Useful for manual transcript mode when wx-cli is unavailable.",
    )
    args = parser.parse_args()
    if args.source == "file" and not args.input_file:
        parser.error("--input-file is required when --source file is used.")
    return args


def run_json(cmd: list[str]) -> Any:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def sanitize_group_name(name: str) -> str:
    sanitized = re.sub(r'[\/\\:\*\?"<>\|\x00-\x1f]', "_", name).rstrip(". ").strip()
    return sanitized or "unnamed-group"


def synthetic_group_id(name: str) -> str:
    stem = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", name).strip("-").lower()
    return f"manual-{stem or 'chat'}"


def parse_iso_date(raw: str) -> date:
    return datetime.strptime(raw, "%Y-%m-%d").date()


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


def build_analysis(
    messages: list[Message],
    stats: dict[str, Any],
    raw_file: Path,
    since: str,
    until: str,
) -> dict[str, Any]:
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
            "since": since,
            "until": until,
            "label": f"{since} ~ {until}",
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
        "source": stats.get("source") or "wx-cli",
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
        f"- Source: `{analysis.get('source', 'wx-cli')}`",
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


def infer_message_type(content: str) -> str:
    stripped = content.strip()
    if not stripped:
        return "文本"
    if stripped.startswith("[系统]") or "撤回了一条消息" in stripped:
        return "系统"
    if stripped.startswith("[图片]"):
        return "图片"
    if stripped.startswith("[视频]"):
        return "视频"
    if stripped.startswith("[表情]"):
        return "表情"
    if stripped.startswith("[链接]") or stripped.startswith("[文件]"):
        return "链接/文件"
    return "文本"


def clean_transcript_line(raw: str) -> str:
    return raw.replace("\ufeff", "").strip()


def is_ignored_transcript_line(line: str) -> bool:
    return clean_transcript_line(line) in IGNORED_TRANSCRIPT_LINES


def strip_transcript_decorators(line: str) -> str:
    return re.sub(r"^[=\-—─·•\s]+|[=\-—─·•\s]+$", "", clean_transcript_line(line))


def resolve_partial_date(month: int, day: int, since: date, until: date) -> date | None:
    candidates: list[tuple[int, int, date]] = []
    for year in sorted({since.year - 1, since.year, until.year, until.year + 1}):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        in_range_penalty = 0 if since <= candidate <= until else 1
        distance = min(abs((candidate - since).days), abs((candidate - until).days))
        candidates.append((in_range_penalty, distance, candidate))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return candidates[0][2]


def parse_transcript_date(line: str, since: date, until: date) -> date | None:
    candidate = strip_transcript_decorators(line)
    if not candidate:
        return None
    full_match = FULL_DATE_RE.match(candidate)
    if full_match:
        try:
            return date(
                int(full_match.group("year")),
                int(full_match.group("month")),
                int(full_match.group("day")),
            )
        except ValueError:
            return None
    partial_match = PARTIAL_DATE_RE.match(candidate)
    if partial_match:
        return resolve_partial_date(
            int(partial_match.group("month")),
            int(partial_match.group("day")),
            since,
            until,
        )
    return None


def normalize_time_token(raw: str) -> tuple[str, int, int, int]:
    match = TIME_TOKEN_RE.match(clean_transcript_line(raw))
    if not match:
        raise ValueError(f"Unrecognized time token: {raw!r}")
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    second = int(match.group("second") or 0)
    prefix = match.group("prefix") or ""
    suffix = (match.group("suffix") or "").lower()

    if suffix == "pm" and hour < 12:
        hour += 12
    elif suffix == "am" and hour == 12:
        hour = 0

    if prefix in {"下午", "晚上"} and 1 <= hour < 12:
        hour += 12
    elif prefix == "中午" and 1 <= hour < 11:
        hour += 12
    elif prefix == "凌晨" and hour == 12:
        hour = 0

    return f"{hour:02d}:{minute:02d}:{second:02d}", hour, minute, second


def next_nonempty_index(lines: list[str], start: int) -> int | None:
    for idx in range(start, len(lines)):
        if clean_transcript_line(lines[idx]):
            return idx
    return None


def parse_header_line(lines: list[str], index: int, since: date, until: date) -> tuple[str, str] | None:
    line = clean_transcript_line(lines[index])
    if not line or is_ignored_transcript_line(line):
        return None
    next_idx = next_nonempty_index(lines, index + 1)
    if next_idx is None:
        return None
    next_line = clean_transcript_line(lines[next_idx])
    if not next_line or parse_transcript_date(next_line, since, until):
        return None

    for pattern in (HEADER_NAME_TIME_RE, HEADER_TIME_NAME_RE):
        match = pattern.match(line)
        if not match:
            continue
        sender = clean_transcript_line(match.group("sender"))
        time_token = clean_transcript_line(match.group("time"))
        if sender:
            return sender, time_token
    return None


def normalize_transcript_body(lines: list[str]) -> str:
    cleaned: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue
        cleaned.append(line)
    while cleaned and cleaned[-1] == "":
        cleaned.pop()
    return "\n".join(cleaned).strip()


def parse_manual_transcript(
    text: str,
    chat_name: str,
    group_id: str,
    since: str,
    until: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not text.strip():
        raise ValueError("Manual transcript is empty.")

    since_date = parse_iso_date(since)
    until_date = parse_iso_date(until)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    current_date = since_date
    manual_messages: list[dict[str, Any]] = []
    local_id = 1

    i = 0
    while i < len(lines):
        line = clean_transcript_line(lines[i])
        if not line or is_ignored_transcript_line(line):
            i += 1
            continue

        parsed_date = parse_transcript_date(line, since_date, until_date)
        if parsed_date:
            current_date = parsed_date
            i += 1
            continue

        header = parse_header_line(lines, i, since_date, until_date)
        if header:
            sender, raw_time = header
            normalized_time, hour, minute, second = normalize_time_token(raw_time)
            body_lines: list[str] = []
            j = i + 1
            while j < len(lines):
                candidate = clean_transcript_line(lines[j])
                if not candidate:
                    if body_lines and body_lines[-1].strip():
                        body_lines.append("")
                    j += 1
                    continue
                if is_ignored_transcript_line(candidate):
                    j += 1
                    continue
                if parse_transcript_date(candidate, since_date, until_date):
                    break
                if parse_header_line(lines, j, since_date, until_date):
                    break
                body_lines.append(lines[j].rstrip())
                j += 1

            content = normalize_transcript_body(body_lines)
            if content:
                message_dt = datetime(
                    current_date.year,
                    current_date.month,
                    current_date.day,
                    hour,
                    minute,
                    second,
                )
                manual_messages.append(
                    {
                        "local_id": local_id,
                        "sender": sender,
                        "time": f"{current_date.isoformat()} {normalized_time[:5]}",
                        "timestamp": int(message_dt.timestamp()) + local_id,
                        "type": infer_message_type(content),
                        "content": content,
                    }
                )
                local_id += 1
                i = j
                continue

        if since_date <= current_date <= until_date:
            message_dt = datetime(
                current_date.year,
                current_date.month,
                current_date.day,
                0,
                0,
                min(local_id, 59),
            )
            manual_messages.append(
                {
                    "local_id": local_id,
                    "sender": "",
                    "time": f"{current_date.isoformat()} 00:00",
                    "timestamp": int(message_dt.timestamp()) + local_id,
                    "type": infer_message_type(line if line.startswith("[系统]") else f"[系统] {line}"),
                    "content": line if line.startswith("[系统]") else f"[系统] {line}",
                }
            )
            local_id += 1
        i += 1

    filtered = [
        item
        for item in manual_messages
        if since <= item["time"][:10] <= until
    ]
    filtered.sort(key=lambda item: (item["timestamp"], item["local_id"]))

    messages = normalize_messages(filtered)
    by_hour = Counter(msg.hour for msg in messages)
    by_type = Counter(msg.type for msg in messages)
    senders = Counter(msg.sender for msg in messages if msg.sender)
    stats_payload = {
        "by_hour": [{"hour": hour, "count": by_hour.get(hour, 0)} for hour in range(24)],
        "by_type": [
            {"type": type_name, "count": count}
            for type_name, count in by_type.most_common()
        ],
        "chat": chat_name,
        "chat_type": "group",
        "is_group": True,
        "top_senders": [
            {"sender": sender, "count": count}
            for sender, count in senders.most_common(15)
        ],
        "total": len(filtered),
        "username": group_id,
        "source": "manual-transcript",
    }
    return filtered, stats_payload


def clipboard_commands() -> list[list[str]]:
    if sys.platform == "darwin":
        return [["pbpaste"]]
    if sys.platform.startswith("win"):
        return [["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"]]

    commands: list[list[str]] = []
    if shutil.which("wl-paste"):
        commands.append(["wl-paste", "-n"])
    if shutil.which("xclip"):
        commands.append(["xclip", "-selection", "clipboard", "-o"])
    if shutil.which("xsel"):
        commands.append(["xsel", "--clipboard", "--output"])
    return commands


def read_clipboard_text() -> str:
    commands = clipboard_commands()
    if not commands:
        raise RuntimeError(
            "No clipboard reader found. Use --source file instead, or install pbpaste / Get-Clipboard / wl-paste / xclip / xsel."
        )

    errors: list[str] = []
    for cmd in commands:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout:
            return result.stdout
        errors.append(f"{' '.join(cmd)} -> {result.stderr.strip() or 'no output'}")
    raise RuntimeError("Clipboard read failed: " + " | ".join(errors))


def read_manual_text(args: argparse.Namespace) -> str:
    if args.source == "clipboard":
        return read_clipboard_text()
    if args.source == "stdin":
        return sys.stdin.read()
    if args.source == "file":
        return Path(args.input_file).expanduser().read_text(encoding="utf-8")
    raise ValueError(f"Unsupported manual source: {args.source}")


def fetch_from_wx_cli(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any], str | None]:
    try:
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
    except subprocess.CalledProcessError as exc:
        cmd = " ".join(str(part) for part in exc.cmd)
        detail = (exc.stderr or exc.stdout or "").strip() or f"exit code {exc.returncode}"
        raise RuntimeError(
            f"{cmd} failed: {detail}\n"
            "If WeChat 4.x blocks wx-cli on this machine, rerun with --source clipboard or --source file."
        ) from exc

    if not isinstance(history_payload, list):
        raise RuntimeError("wx history did not return a JSON array.")
    if not isinstance(stats_payload, dict):
        raise RuntimeError("wx stats did not return a JSON object.")
    stats_payload["source"] = "wx-cli"
    return history_payload, stats_payload, None


def fetch_from_manual_source(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    transcript_text = read_manual_text(args)
    group_id = args.group_id or synthetic_group_id(args.chat)
    history_payload, stats_payload = parse_manual_transcript(
        transcript_text,
        args.chat,
        group_id,
        args.since,
        args.until,
    )
    return history_payload, stats_payload, transcript_text


def build_bundle(args: argparse.Namespace) -> dict[str, Any]:
    if args.source == "wx-cli":
        history_payload, stats_payload, transcript_text = fetch_from_wx_cli(args)
    else:
        history_payload, stats_payload, transcript_text = fetch_from_manual_source(args)

    messages = normalize_messages(history_payload)
    group_name = stats_payload.get("chat") or args.chat
    group_id = stats_payload.get("username") or args.group_id or synthetic_group_id(group_name)
    group_dir = Path(args.data_root).expanduser().resolve() / f"{group_id}-{sanitize_group_name(group_name)}"
    raw_dir = group_dir / "raw"
    analysis_dir = group_dir / "analysis"
    raw_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    slug = f"{args.since}_{args.until}"
    raw_messages_file = raw_dir / f"{slug}.messages.json"
    raw_stats_file = raw_dir / f"{slug}.stats.json"
    raw_transcript_file = raw_dir / f"{slug}.transcript.txt"
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
    if transcript_text is not None:
        raw_transcript_file.write_text(transcript_text, encoding="utf-8")

    analysis = build_analysis(messages, stats_payload, raw_messages_file, args.since, args.until)
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
        "source": args.source,
    }
    if transcript_text is not None:
        result["raw_transcript_txt"] = str(raw_transcript_file)
    return result


def main() -> None:
    args = parse_args()
    result = build_bundle(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
