#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from newspaper_bridge import render as render_newspaper_site
from newspaper_bridge import render_html as render_newspaper_html


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a newspaper-style local WeChat web daily."
    )
    parser.add_argument("--summary", required=True, help="Path to summary.json")
    parser.add_argument("--analysis", required=True, help="Path to analysis.json")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def peak_day_label(analysis: dict[str, Any]) -> str:
    peak = analysis.get("peak_day") or {}
    date = peak.get("date") or ""
    count = peak.get("count") or 0
    if not date:
        return ""
    return f"{date[5:]} ({count} 条)"


def period_verdict(summary: dict[str, Any]) -> str:
    return summary.get("period_in_one_line") or summary.get("week_in_one_line") or ""


def effective_verdict(summary: dict[str, Any], analysis: dict[str, Any]) -> str:
    explicit = period_verdict(summary).strip()
    if explicit:
        return explicit
    last_message_time = analysis.get("last_message_time") or analysis.get("date_range", {}).get("until") or ""
    if analysis.get("total_messages", 0) == 0:
        return f"截至 {last_message_time or summary['time_range']}，这一版暂无可成稿的新消息。"
    return f"{summary['group_name']} 在 {summary['time_range']} 内形成了可复盘的讨论主线。"


def fallback_threads(summary: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, str]]:
    if summary.get("main_threads"):
        return summary["main_threads"]
    time_range = summary.get("time_range") or analysis.get("date_range", {}).get("label", "")
    total_messages = analysis.get("total_messages", 0)
    if total_messages == 0:
        return [
            {
                "title": "这一版暂时无新稿",
                "summary": f"{time_range} 这一段截至生成时没有抓到新消息，所以本页保留成一张静版快照。",
            },
            {
                "title": "统计栏仍可作为对照",
                "summary": "虽然没有形成新话题，但消息数、参与人数、字符数和时间范围仍然被完整记录，后续重跑可以直接比较变化。",
            },
        ]
    return [
        {
            "title": "主线待补齐",
            "summary": "分析材料已经就位，但这一版 summary 还没有整理出足够清晰的主线，可以回到 briefing 和原话继续补稿。",
        }
    ]


def fallback_people(summary: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, str]]:
    if summary.get("people"):
        return summary["people"]
    top_senders = analysis.get("top_senders", [])[:4]
    if top_senders:
        return [
            {
                "name": item.get("name", "未知成员"),
                "tag": f"{item.get('count', 0)} 条 / 活跃发送",
                "desc": "这一版没有单独写人物观察，先用发送活跃度保留现场感。",
            }
            for item in top_senders
        ]
    return [
        {
            "name": "群聊现场",
            "tag": "静版",
            "desc": "今天没有出现足够成型的人物线索，所以人物栏保持克制留白。",
        }
    ]


def fallback_timeline(summary: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, Any]]:
    if summary.get("timeline"):
        return summary["timeline"]
    date_range = analysis.get("date_range", {})
    date_label = date_range.get("until") or summary.get("time_range", "")
    if analysis.get("total_messages", 0) == 0:
        return [
            {
                "date": date_label,
                "label": "静版",
                "bullets": [
                    "当天截至抓取时点没有形成新讨论。",
                    "这份页面保留了当前群聊状态，方便后续补跑对照。",
                ],
            }
        ]
    return [
        {
            "date": date_label,
            "label": "待补稿",
            "bullets": ["analysis 已生成，但这条时间线还没有被整理成编辑版摘要。"],
        }
    ]


def fallback_quotes(summary: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, str]]:
    if summary.get("quotes"):
        return summary["quotes"]
    if summary.get("opening"):
        return [{"text": summary["opening"], "who": f"{summary['group_name']} / lead"}]
    return [{"text": effective_verdict(summary, analysis), "who": f"{summary['group_name']} / edition note"}]


def fallback_links(summary: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, str]]:
    if summary.get("links"):
        return summary["links"]
    if analysis.get("total_messages", 0) == 0:
        return [{"title": "暂无新增资源", "note": "这一天没有出现需要单列存档的链接或工具资源。"}]
    return [{"title": "资源栏待补", "note": "如果本段讨论里出现工具、文章或 repo，可在这里补成资料栏。"}]


def fallback_next_actions(summary: dict[str, Any], analysis: dict[str, Any]) -> list[str]:
    if summary.get("next_actions"):
        return summary["next_actions"]
    if analysis.get("total_messages", 0) == 0:
        return [
            "当天有新消息后，重跑同一时间范围，静版会自动变成真正可读的日报。",
            "如果需要连续观察，可把范围改成 3d 或 7d，再看是否形成清晰主线。",
        ]
    return ["回到 briefing 和原话，补齐这一版最值得保留的 4 到 6 条主线。"]


def render_list(items: list[str]) -> str:
    return "".join(f"<li>{html.escape(item)}</li>" for item in items)


def render_stat_rows(summary: dict[str, Any], analysis: dict[str, Any], generated_at: str) -> str:
    rows = [
        ("群聊", summary.get("group_name", "")),
        ("时间范围", summary.get("time_range", "")),
        ("生成时间", generated_at),
        ("总消息数", str(analysis.get("total_messages", 0))),
        ("参与人数", str(analysis.get("active_senders", 0))),
        ("总字符数", str(analysis.get("char_count", 0))),
        ("高峰日", peak_day_label(analysis) or "暂无"),
    ]
    return "".join(
        f"<div class='stat-row'><dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd></div>"
        for label, value in rows
    )


def render_leader_rows(analysis: dict[str, Any]) -> str:
    leaders = analysis.get("top_senders", [])[:6]
    if not leaders:
        leaders = [{"name": "今日无排行", "count": 0}]
    return "".join(
        "<li>"
        f"<span>{html.escape(str(item.get('name', '未知成员')))}</span>"
        f"<strong>{item.get('count', 0)}</strong>"
        "</li>"
        for item in leaders
    )


def markdown_report(summary: dict[str, Any], analysis: dict[str, Any]) -> str:
    verdict = effective_verdict(summary, analysis)
    threads = fallback_threads(summary, analysis)
    people = fallback_people(summary, analysis)
    timeline = fallback_timeline(summary, analysis)
    quotes = fallback_quotes(summary, analysis)
    links = fallback_links(summary, analysis)
    next_actions = fallback_next_actions(summary, analysis)

    lines = [
        f"{summary['group_name']} 群聊日报 · 网页报纸版 · {summary['time_range']}",
        "",
        "消息统计",
        "",
        f"- 总消息数：{analysis['total_messages']}",
        f"- 参与人数：{analysis['active_senders']}",
        f"- 总字符数：{analysis['char_count']}",
    ]
    peak = peak_day_label(analysis)
    if peak:
        lines.append(f"- 高峰日：{peak}")

    lines.extend(["", "活跃成员 Top 10", ""])
    for idx, item in enumerate(analysis.get("top_senders", [])[:10], start=1):
        lines.append(f"{idx}. {item['name']}：{item['count']}")

    lines.extend(["", summary["opening"], "", "本版主线", ""])
    for idx, thread in enumerate(threads, start=1):
        lines.append(f"{idx}. {thread['title']}")
        lines.append(f"   {thread['summary']}")
        lines.append("")

    lines.append("群像")
    lines.append("")
    for person in people:
        lines.append(f"- {person['name']}｜{person['tag']}")
        lines.append(f"  {person['desc']}")
    lines.append("")

    lines.append("时间切片")
    lines.append("")
    for item in timeline:
        lines.append(f"- {item['date']} {item['label']}")
        for bullet in item.get("bullets", []):
            lines.append(f"  - {bullet}")
    lines.append("")

    lines.append("引语栏")
    lines.append("")
    for quote in quotes:
        lines.append(f"- “{quote['text']}” —— {quote['who']}")
    lines.append("")

    lines.extend(["本版判断", "", verdict, "", "资料栏", ""])
    for item in links:
        lines.append(f"- {item['title']}：{item['note']}")
    lines.append("")

    lines.append("续稿线索")
    lines.append("")
    for item in next_actions:
        lines.append(f"- {item}")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_html(summary: dict[str, Any], analysis: dict[str, Any]) -> str:
    return render_newspaper_html(summary, analysis)


def main() -> None:
    args = parse_args()
    summary_path = Path(args.summary).expanduser().resolve()
    analysis_path = Path(args.analysis).expanduser().resolve()
    summary = read_json(summary_path)
    analysis = read_json(analysis_path)

    group_dir = analysis_path.parent.parent
    slug = f"{analysis['date_range']['since']}_{analysis['date_range']['until']}"
    markdown_path = group_dir / f"{slug}.web.md"
    summary_copy_path = group_dir / "summary.json"
    history_path = group_dir / "history.json"
    history_log_path = group_dir / "history-digests.jsonl"

    markdown_text = markdown_report(summary, analysis)
    render_result = render_newspaper_site(summary_path, analysis_path)

    markdown_path.write_text(markdown_text, encoding="utf-8")
    summary_copy_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    history_payload = {
        "group_id": summary["group_id"],
        "group_name": summary["group_name"],
        "folder": group_dir.name,
        "last_digest": {
            "file": markdown_path.name,
            "date_range": summary["time_range"],
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "message_count": analysis["total_messages"],
            "last_message_time": analysis.get("last_message_time") or analysis["date_range"]["until"],
            "site_entry": "dist/index.html",
            "mode": "webpage",
        },
    }
    history_path.write_text(
        json.dumps(history_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with history_log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(history_payload["last_digest"], ensure_ascii=False) + "\n")

    print(
        json.dumps(
            {
                "markdown": str(markdown_path),
                "site_index": render_result["promoted_site_index"],
                "dist_index": render_result["promoted_dist_index"],
                "range_dir": render_result["range_dir"],
                "story_json": render_result["story_json"],
                "layout_plan_json": render_result["layout_plan_json"],
                "pdf": render_result["pdf"],
                "history_json": str(history_path),
                "summary_json": str(summary_copy_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
