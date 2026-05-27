#!/usr/bin/env python3
"""Batch generate IGN AI daily reports for all available dates.

Extracts daily messages from weekly raw files, generates analysis.json,
and renders the community-style daily report HTML.

Usage:
  python batch_ignai_daily.py --group-dir /path/to/group/dir
  python batch_ignai_daily.py --group-dir /path/to/group/dir --only-missing
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Batch generate IGN AI daily reports")
    p.add_argument("--group-dir", required=True, help="Path to group chat directory")
    p.add_argument("--only-missing", action="store_true", help="Only generate for dates without existing analysis")
    p.add_argument("--render-script", help="Path to render_ignai_daily.py")
    return p.parse_args()


def extract_daily_messages(raw_dir: Path, target_date: str) -> list[dict]:
    """Extract messages for a specific date from weekly raw message files."""
    messages = []
    for msg_file in sorted(raw_dir.glob("*.messages.json")):
        try:
            data = json.loads(msg_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        for msg in data:
            time_str = msg.get("time", "")
            if isinstance(time_str, str) and time_str.startswith(target_date):
                messages.append(msg)
            elif isinstance(msg.get("timestamp"), (int, float)):
                ts = msg["timestamp"]
                dt = datetime.fromtimestamp(ts)
                if dt.strftime("%Y-%m-%d") == target_date:
                    messages.append(msg)

    return messages


def generate_analysis(messages: list[dict], group_name: str, group_id: str, target_date: str) -> dict:
    """Generate analysis.json from daily messages."""
    if not messages:
        return {
            "group_name": group_name,
            "group_id": group_id,
            "date_range": {"since": target_date, "until": target_date, "label": f"{target_date} ~ {target_date}"},
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "total_messages": 0,
            "active_senders": 0,
            "char_count": 0,
            "by_type": {},
            "peak_day": {"date": target_date, "count": 0},
            "peak_hour": {"hour": 0, "count": 0},
            "top_senders": [],
            "daily_breakdown": [],
            "keyword_hits": [],
            "quote_candidates": [],
            "frequent_links": [],
        }

    # Basic stats
    total = len(messages)
    senders = set()
    char_count = 0
    by_type = Counter()
    sender_counts = Counter()
    hour_counts = Counter()
    keyword_counts = Counter()
    links = []
    quotes = []

    # AI/tool keywords to track
    ai_keywords = [
        "OpenAI", "Claude", "Gemini", "GPT", "API", "Agent", "token", "Codex",
        "Kimi", "DeepSeek", "Qwen", "通义", "千问", "Llama", "Mistral",
        "Cursor", "Copilot", "Windsurf", "Replit", "v0", "Bolt",
        "Midjourney", "SD", "Stable Diffusion", "DALL-E", "Sora",
        "LangChain", "Dify", "Coze", "扣子", "n8n",
        "模型", "大模型", "LLM", "RAG", "向量", "embedding",
        "部署", "服务器", "云", "阿里云", "腾讯云", "AWS",
        "黑客松", "hackathon", "比赛", "竞赛",
        "Agent", "skill", "workflow", "自动化",
    ]

    for msg in messages:
        sender = msg.get("sender", "未知")
        content = msg.get("content", "")
        msg_type = msg.get("type", "文本")

        senders.add(sender)
        sender_counts[sender] += 1
        by_type[msg_type] += 1

        # Char count for text messages
        if msg_type == "文本":
            char_count += len(content)

        # Hour distribution
        time_str = msg.get("time", "")
        if len(time_str) >= 13:
            try:
                hour = int(time_str[11:13])
                hour_counts[hour] += 1
            except (ValueError, IndexError):
                pass

        # Keyword extraction
        content_lower = content.lower()
        for kw in ai_keywords:
            if kw.lower() in content_lower:
                keyword_counts[kw] += 1

        # Link extraction
        if "http://" in content or "https://" in content:
            import re
            urls = re.findall(r'https?://[^\s<>"\']+', content)
            for url in urls:
                # Try to get title from content around the URL
                title = url[:80]
                links.append({"title": title, "url": url, "count": 1})

        # Quote candidates (messages with substance)
        if len(content) > 20 and msg_type == "文本" and not content.startswith("<?xml"):
            quotes.append({
                "text": content[:200],
                "sender": sender,
                "time": time_str,
            })

    # Aggregate links by URL
    link_counter = Counter()
    link_map = {}
    for link in links:
        url = link["url"]
        link_counter[url] += 1
        if url not in link_map:
            link_map[url] = link

    frequent_links = []
    for url, count in link_counter.most_common(10):
        entry = link_map[url].copy()
        entry["count"] = count
        frequent_links.append(entry)

    # Peak hour
    peak_hour = hour_counts.most_common(1)
    peak_h = peak_hour[0] if peak_hour else (0, 0)

    # Top senders
    top_senders = [{"name": name, "count": count} for name, count in sender_counts.most_common(15)]

    # Keyword hits
    keyword_hits = [{"keyword": kw, "count": count} for kw, count in keyword_counts.most_common(15)]

    # First/last message times
    times = [msg.get("time", "") for msg in messages if msg.get("time")]
    times.sort()
    first_time = times[0] if times else f"{target_date} 00:00"
    last_time = times[-1] if times else f"{target_date} 23:59"

    return {
        "group_name": group_name,
        "group_id": group_id,
        "date_range": {"since": target_date, "until": target_date, "label": f"{target_date} ~ {target_date}"},
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "total_messages": total,
        "active_senders": len(senders),
        "char_count": char_count,
        "first_message_time": first_time,
        "last_message_time": last_time,
        "by_type": dict(by_type),
        "peak_day": {"date": target_date, "count": total},
        "peak_hour": {"hour": peak_h[0], "count": peak_h[1]},
        "top_senders": top_senders,
        "daily_breakdown": [{
            "date": target_date,
            "total": total,
            "char_count": char_count,
            "by_type": dict(by_type),
            "top_senders": top_senders[:5],
        }],
        "keyword_hits": keyword_hits,
        "quote_candidates": quotes[:20],
        "frequent_links": frequent_links,
    }


def get_existing_dates(analysis_dir: Path) -> set[str]:
    """Get dates that already have daily analysis files."""
    dates = set()
    for f in analysis_dir.glob("*_*.analysis.json"):
        name = f.stem  # e.g., "2026-05-26_2026-05-26.analysis"
        parts = name.split("_")
        if len(parts) >= 2 and parts[0] == parts[1].split(".")[0]:
            dates.add(parts[0])
    return dates


def get_weekday_range(start: str, end: str) -> list[str]:
    """Get all weekday dates in range."""
    from datetime import date
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    dates = []
    while s <= e:
        if s.weekday() < 5:  # Mon-Fri
            dates.append(s.isoformat())
        s += timedelta(days=1)
    return dates


def main() -> None:
    args = parse_args()
    group_dir = Path(args.group_dir).expanduser().resolve()
    raw_dir = group_dir / "raw"
    analysis_dir = group_dir / "analysis"
    dist_dir = group_dir / "dist"

    if not raw_dir.exists():
        print(f"Error: raw directory not found at {raw_dir}", file=sys.stderr)
        sys.exit(1)

    # Determine group info from existing analysis
    existing_analysis = list(analysis_dir.glob("*.analysis.json"))
    group_name = "IGN AI | 洋来"
    group_id = "43663749608@chatroom"
    if existing_analysis:
        try:
            data = json.loads(existing_analysis[0].read_text(encoding="utf-8"))
            group_name = data.get("group_name", group_name)
            group_id = data.get("group_id", group_id)
        except Exception:
            pass

    # Determine date range from raw files
    all_dates = set()
    for msg_file in raw_dir.glob("*.messages.json"):
        name = msg_file.stem
        parts = name.split("_")
        if len(parts) >= 2:
            start = parts[0]
            end = parts[1].split(".")[0]
            all_dates.update(get_weekday_range(start, end))

    if not all_dates:
        print("No dates found in raw data", file=sys.stderr)
        sys.exit(1)

    min_date = min(all_dates)
    max_date = max(all_dates)
    print(f"Date range from raw data: {min_date} ~ {max_date}")
    print(f"Total weekdays: {len(all_dates)}")

    # Check existing
    existing = get_existing_dates(analysis_dir)
    print(f"Existing daily analysis: {len(existing)} dates")

    # Determine which dates to process
    if args.only_missing:
        target_dates = sorted(all_dates - existing)
        print(f"Missing dates to generate: {len(target_dates)}")
    else:
        target_dates = sorted(all_dates)
        print(f"All dates to generate: {len(target_dates)}")

    if not target_dates:
        print("All dates already have analysis files!")
        return

    # Find render script
    render_script = args.render_script
    if not render_script:
        # Try to find it relative to this script
        script_dir = Path(__file__).parent
        candidate = script_dir / "render_ignai_daily.py"
        if candidate.exists():
            render_script = str(candidate)

    # Process each date
    generated = []
    for date_str in target_dates:
        print(f"\n--- Processing {date_str} ---")

        # Extract daily messages
        messages = extract_daily_messages(raw_dir, date_str)
        print(f"  Messages: {len(messages)}")

        if not messages:
            print(f"  Skipping (no messages)")
            continue

        # Generate analysis
        analysis = generate_analysis(messages, group_name, group_id, date_str)

        # Save analysis.json
        analysis_file = analysis_dir / f"{date_str}_{date_str}.analysis.json"
        analysis_file.write_text(json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  Saved: {analysis_file.name}")

        # Generate briefing.md
        briefing = generate_briefing(analysis, messages)
        briefing_file = analysis_dir / f"{date_str}_{date_str}.briefing.md"
        briefing_file.write_text(briefing, encoding="utf-8")

        # Render HTML
        if render_script:
            out_file = dist_dir / f"ignai-daily-{date_str}.html"
            try:
                result = subprocess.run(
                    [sys.executable, render_script,
                     "--analysis", str(analysis_file),
                     "-o", str(out_file)],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    print(f"  HTML: {out_file.name}")
                    generated.append(date_str)
                else:
                    print(f"  Render error: {result.stderr[:200]}")
            except Exception as ex:
                print(f"  Render exception: {ex}")
        else:
            generated.append(date_str)

    print(f"\n=== Done: {len(generated)} daily reports generated ===")
    for d in generated:
        print(f"  {d}")


def generate_briefing(analysis: dict, messages: list[dict]) -> str:
    """Generate a briefing.md from analysis data."""
    group_name = analysis.get("group_name", "IGN AI")
    dr = analysis.get("date_range", {})
    date_str = dr.get("since", "")

    lines = [
        f"# {group_name} · Daily Briefing",
        "",
        f"- Date: `{date_str}`",
        f"- Total messages: `{analysis.get('total_messages', 0)}`",
        f"- Active senders: `{analysis.get('active_senders', 0)}`",
        f"- Total text chars: `{analysis.get('char_count', 0)}`",
        f"- Peak hour: `{analysis.get('peak_hour', {}).get('hour', '')}:00` ({analysis.get('peak_hour', {}).get('count', 0)} messages)",
        "",
        "## Top Senders",
        "",
    ]

    for ts in analysis.get("top_senders", [])[:10]:
        lines.append(f"- {ts['name']}: {ts['count']}")

    lines.extend(["", "## Keyword Hits", ""])
    for kw in analysis.get("keyword_hits", [])[:10]:
        lines.append(f"- {kw['keyword']}: {kw['count']}")

    if analysis.get("frequent_links"):
        lines.extend(["", "## Frequent Links", ""])
        for fl in analysis["frequent_links"][:5]:
            lines.append(f"- {fl.get('title', fl.get('url', ''))} ({fl.get('count', 1)}x)")

    lines.extend(["", "## Quote Candidates", ""])
    for q in analysis.get("quote_candidates", [])[:5]:
        lines.append(f"- {q.get('time', '')} · {q.get('sender', '')}: {q.get('text', '')[:100]}")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
