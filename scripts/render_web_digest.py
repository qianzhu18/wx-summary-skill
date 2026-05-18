#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any


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
    generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    verdict = effective_verdict(summary, analysis)
    threads = fallback_threads(summary, analysis)
    people = fallback_people(summary, analysis)
    timeline = fallback_timeline(summary, analysis)
    quotes = fallback_quotes(summary, analysis)
    links = fallback_links(summary, analysis)
    next_actions = fallback_next_actions(summary, analysis)
    deck = summary.get("subheadline") or verdict
    opening = summary.get("opening") or deck
    peak = peak_day_label(analysis) or "暂无高峰日"

    people_html = "".join(
        (
            "<article class='mini-article'>"
            f"<div class='kicker'>群像 {idx:02d}</div>"
            f"<h3>{html.escape(person['name'])}</h3>"
            f"<div class='meta'>{html.escape(person['tag'])}</div>"
            f"<p>{html.escape(person['desc'])}</p>"
            "</article>"
        )
        for idx, person in enumerate(people, start=1)
    )
    threads_html = "".join(
        (
            "<article class='story'>"
            f"<div class='kicker'>主线 {idx:02d}</div>"
            f"<h3>{html.escape(thread['title'])}</h3>"
            f"<p>{html.escape(thread['summary'])}</p>"
            "</article>"
        )
        for idx, thread in enumerate(threads, start=1)
    )
    timeline_html = "".join(
        (
            "<article class='timeline-item'>"
            f"<h3>{html.escape(item['date'])}</h3>"
            f"<div class='timeline-label'>{html.escape(item['label'])}</div>"
            f"<ul>{render_list(item.get('bullets', []))}</ul>"
            "</article>"
        )
        for item in timeline
    )
    quotes_html = "".join(
        (
            "<blockquote class='quote-item'>"
            f"<p>{html.escape(quote['text'])}</p>"
            f"<footer>{html.escape(quote['who'])}</footer>"
            "</blockquote>"
        )
        for quote in quotes
    )
    links_html = "".join(
        (
            "<article class='resource-item'>"
            f"<h3>{html.escape(item['title'])}</h3>"
            f"<p>{html.escape(item['note'])}</p>"
            "</article>"
        )
        for item in links
    )
    next_actions_html = "".join(
        f"<li>{html.escape(item)}</li>" for item in next_actions
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(summary['group_name'])} - 群聊日报</title>
  <style>
    :root {{
      --page-bg: #efe7d8;
      --paper: #fbf8f1;
      --ink: #191612;
      --muted: #5c5347;
      --line: #c9bb9e;
      --accent: #9c2d20;
      --max: 1360px;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      background: var(--page-bg);
      color: var(--ink);
      font-family: "Songti SC", "Noto Serif SC", "Source Han Serif SC", Georgia, serif;
      line-height: 1.65;
    }}

    .paper {{
      width: min(calc(100% - 24px), var(--max));
      margin: 12px auto;
      background: var(--paper);
      border: 1px solid #b9aa8b;
      box-shadow: 0 20px 60px rgba(49, 38, 24, 0.12);
    }}

    .inner {{
      padding: 0 28px;
    }}

    .topline,
    .meta-strip,
    .section-head,
    .footer-note {{
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Noto Sans SC", "Helvetica Neue", sans-serif;
    }}

    .topline {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      padding: 14px 28px 12px;
      border-bottom: 1px solid var(--line);
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}

    .topline span:nth-child(2) {{
      text-align: center;
    }}

    .topline span:last-child {{
      text-align: right;
    }}

    .masthead {{
      padding: 18px 28px 22px;
      border-bottom: 3px double var(--line);
    }}

    .masthead-grid {{
      display: grid;
      grid-template-columns: 220px minmax(0, 1fr) 220px;
      gap: 18px;
      align-items: end;
    }}

    .masthead-side {{
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Noto Sans SC", "Helvetica Neue", sans-serif;
      font-size: 13px;
      color: var(--muted);
    }}

    .masthead-side strong {{
      display: block;
      color: var(--ink);
      font-size: 20px;
      margin-top: 6px;
    }}

    .brand {{
      text-align: center;
    }}

    .brand-mark {{
      font-size: 58px;
      line-height: 1;
      letter-spacing: 0;
      font-weight: 700;
    }}

    .brand-sub {{
      margin-top: 10px;
      font-size: 12px;
      color: var(--accent);
      letter-spacing: 0.22em;
      text-transform: uppercase;
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Noto Sans SC", "Helvetica Neue", sans-serif;
    }}

    .meta-strip {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      padding: 12px 0 0;
      font-size: 13px;
      color: var(--muted);
    }}

    .meta-strip div {{
      border-top: 1px solid var(--line);
      padding-top: 10px;
    }}

    .meta-strip strong {{
      display: block;
      color: var(--ink);
      font-size: 16px;
      margin-top: 4px;
    }}

    .front-page {{
      padding: 28px 28px 20px;
      border-bottom: 1px solid var(--line);
    }}

    .front-grid {{
      display: grid;
      grid-template-columns: minmax(0, 2.1fr) minmax(280px, 0.9fr);
      gap: 26px;
    }}

    .lead-story {{
      padding-right: 26px;
      border-right: 1px solid var(--line);
    }}

    .kicker {{
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Noto Sans SC", "Helvetica Neue", sans-serif;
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      margin-bottom: 12px;
    }}

    .lead-story h1 {{
      margin: 0;
      font-size: clamp(36px, 5vw, 68px);
      line-height: 1.06;
      letter-spacing: 0;
      text-wrap: balance;
    }}

    .deck {{
      margin: 16px 0 0;
      font-size: 23px;
      line-height: 1.4;
      color: #2e271f;
    }}

    .lead {{
      margin: 22px 0 0;
      font-size: 18px;
      color: var(--muted);
      max-width: 44em;
    }}

    .right-rail {{
      display: grid;
      gap: 18px;
      align-content: start;
    }}

    .rail-box {{
      border-top: 3px solid var(--ink);
      border-bottom: 1px solid var(--line);
      padding: 14px 0 12px;
    }}

    .rail-box h2,
    .section-head h2,
    .section-head h3 {{
      margin: 0;
      font-size: 14px;
      color: var(--accent);
      letter-spacing: 0.12em;
      text-transform: uppercase;
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Noto Sans SC", "Helvetica Neue", sans-serif;
    }}

    .verdict {{
      margin: 10px 0 0;
      font-size: 26px;
      line-height: 1.35;
    }}

    .stat-board {{
      margin: 12px 0 0;
      display: grid;
      gap: 8px;
    }}

    .stat-row {{
      display: grid;
      grid-template-columns: 94px minmax(0, 1fr);
      gap: 10px;
      padding-top: 8px;
      border-top: 1px dotted var(--line);
    }}

    .stat-row dt {{
      margin: 0;
      color: var(--muted);
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Noto Sans SC", "Helvetica Neue", sans-serif;
      font-size: 13px;
    }}

    .stat-row dd {{
      margin: 0;
      font-size: 17px;
    }}

    .leader-list,
    .continuation ul {{
      list-style: none;
      margin: 12px 0 0;
      padding: 0;
    }}

    .leader-list li {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 0;
      border-top: 1px dotted var(--line);
      font-size: 16px;
    }}

    .leader-list span {{
      color: var(--muted);
    }}

    .verdict-strip {{
      padding: 16px 28px;
      border-bottom: 1px solid var(--line);
      border-top: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.35);
    }}

    .verdict-strip p {{
      margin: 0;
      font-size: 22px;
      font-weight: 600;
    }}

    .section {{
      padding: 24px 28px 26px;
      border-bottom: 1px solid var(--line);
    }}

    .section-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: baseline;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--line);
      margin-bottom: 18px;
    }}

    .section-head p {{
      margin: 0;
      font-size: 13px;
      color: var(--muted);
    }}

    .thread-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 20px;
    }}

    .story,
    .mini-article,
    .timeline-item,
    .resource-item,
    .quote-item {{
      min-width: 0;
    }}

    .story {{
      padding-right: 18px;
      border-right: 1px solid var(--line);
    }}

    .story:last-child {{
      border-right: 0;
      padding-right: 0;
    }}

    .story h3,
    .mini-article h3,
    .timeline-item h3,
    .resource-item h3 {{
      margin: 0 0 10px;
      font-size: 26px;
      line-height: 1.2;
      text-wrap: balance;
    }}

    .story p,
    .mini-article p,
    .resource-item p,
    .quote-item p {{
      margin: 0;
      font-size: 17px;
      color: #2b241c;
    }}

    .middle-grid,
    .bottom-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
      gap: 24px;
    }}

    .stack {{
      display: grid;
      gap: 18px;
    }}

    .mini-article,
    .timeline-item,
    .resource-item,
    .quote-item {{
      padding-bottom: 16px;
      border-bottom: 1px dotted var(--line);
    }}

    .mini-article .meta,
    .timeline-label,
    .quote-item footer {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Noto Sans SC", "Helvetica Neue", sans-serif;
    }}

    .timeline-item ul {{
      margin: 12px 0 0;
      padding-left: 18px;
    }}

    .timeline-item li,
    .continuation li {{
      margin: 0 0 8px;
      font-size: 16px;
    }}

    .quote-item {{
      position: relative;
      padding-left: 20px;
    }}

    .quote-item::before {{
      content: "";
      position: absolute;
      left: 0;
      top: 2px;
      bottom: 18px;
      width: 4px;
      background: var(--accent);
    }}

    .continuation {{
      padding: 24px 28px 28px;
      background: rgba(156, 45, 32, 0.04);
      border-top: 1px solid var(--line);
    }}

    .continuation ul {{
      display: grid;
      gap: 10px;
    }}

    .continuation li {{
      padding-top: 10px;
      border-top: 1px dotted var(--line);
    }}

    .footer-note {{
      padding: 18px 28px 26px;
      color: var(--muted);
      font-size: 13px;
    }}

    @media (max-width: 1100px) {{
      .masthead-grid,
      .front-grid,
      .thread-grid,
      .middle-grid,
      .bottom-grid,
      .meta-strip,
      .topline {{
        grid-template-columns: 1fr;
      }}

      .topline span,
      .topline span:nth-child(2),
      .topline span:last-child {{
        text-align: left;
      }}

      .lead-story {{
        padding-right: 0;
        border-right: 0;
        border-bottom: 1px solid var(--line);
        padding-bottom: 20px;
      }}

      .story {{
        border-right: 0;
        padding-right: 0;
        padding-bottom: 16px;
        border-bottom: 1px dotted var(--line);
      }}
    }}
  </style>
</head>
<body>
  <main class="paper">
    <div class="topline">
      <span>第 1 版 / 群聊日报</span>
      <span>People Daily Web Edition</span>
      <span>{html.escape(generated_at)}</span>
    </div>

    <header class="masthead">
      <div class="masthead-grid">
        <div class="masthead-side">
          报别
          <strong>{html.escape(summary['group_name'])}</strong>
        </div>
        <div class="brand">
          <div class="brand-mark">群聊日报</div>
          <div class="brand-sub">People Daily Inspired Web Edition</div>
        </div>
        <div class="masthead-side">
          版次
          <strong>{html.escape(summary['time_range'])}</strong>
        </div>
      </div>
      <div class="meta-strip">
        <div>头条<strong>{html.escape(summary['headline'])}</strong></div>
        <div>判断<strong>{html.escape(verdict)}</strong></div>
        <div>高峰日<strong>{html.escape(peak)}</strong></div>
        <div>来源<strong>真实微信群消息 / 本地静态版</strong></div>
      </div>
    </header>

    <section class="front-page">
      <div class="front-grid">
        <article class="lead-story">
          <div class="kicker">头版导读</div>
          <h1>{html.escape(summary['headline'])}</h1>
          <p class="deck">{html.escape(deck)}</p>
          <p class="lead">{html.escape(opening)}</p>
        </article>
        <aside class="right-rail">
          <section class="rail-box">
            <h2>本版判断</h2>
            <p class="verdict">{html.escape(verdict)}</p>
          </section>
          <section class="rail-box">
            <h2>统计栏</h2>
            <dl class="stat-board">{render_stat_rows(summary, analysis, generated_at)}</dl>
          </section>
          <section class="rail-box">
            <h2>活跃席位</h2>
            <ul class="leader-list">{render_leader_rows(analysis)}</ul>
          </section>
        </aside>
      </div>
    </section>

    <section class="verdict-strip">
      <p>{html.escape(verdict)}</p>
    </section>

    <section class="section">
      <div class="section-head">
        <h2>本版主线</h2>
        <p>用 4 到 6 条真正值得保留的线索重建这段聊天。</p>
      </div>
      <div class="thread-grid">{threads_html}</div>
    </section>

    <section class="section">
      <div class="middle-grid">
        <div>
          <div class="section-head">
            <h2>群像栏</h2>
            <p>只写这段时间里真正能观察到的角色和动作。</p>
          </div>
          <div class="stack">{people_html}</div>
        </div>
        <div>
          <div class="section-head">
            <h2>时间切片</h2>
            <p>保留这段时间的节奏，而不是把所有细节摊平。</p>
          </div>
          <div class="stack">{timeline_html}</div>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="bottom-grid">
        <div>
          <div class="section-head">
            <h2>引语栏</h2>
            <p>只留下真正在群里出现过的语气和原话。</p>
          </div>
          <div class="stack">{quotes_html}</div>
        </div>
        <div>
          <div class="section-head">
            <h2>资料栏</h2>
            <p>把工具、文章、repo 或资源单独存档。</p>
          </div>
          <div class="stack">{links_html}</div>
        </div>
      </div>
    </section>

    <section class="continuation">
      <div class="section-head">
        <h3>续稿线索</h3>
        <p>给下一版留下明确的跟进方向。</p>
      </div>
      <ul>{next_actions_html}</ul>
    </section>

    <footer class="footer-note">
      基于真实微信群消息生成。本地保留 analysis、history 和静态 HTML，方便继续复查、续稿或改版。
    </footer>
  </main>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    summary_path = Path(args.summary).expanduser().resolve()
    analysis_path = Path(args.analysis).expanduser().resolve()
    summary = read_json(summary_path)
    analysis = read_json(analysis_path)

    group_dir = analysis_path.parent.parent
    site_dir = group_dir / "site"
    dist_dir = group_dir / "dist"
    site_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)

    slug = f"{analysis['date_range']['since']}_{analysis['date_range']['until']}"
    markdown_path = group_dir / f"{slug}.web.md"
    summary_copy_path = group_dir / "summary.json"
    site_index_path = site_dir / "index.html"
    dist_index_path = dist_dir / "index.html"
    history_path = group_dir / "history.json"
    history_log_path = group_dir / "history-digests.jsonl"

    markdown_text = markdown_report(summary, analysis)
    html_text = render_html(summary, analysis)

    markdown_path.write_text(markdown_text, encoding="utf-8")
    summary_copy_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    site_index_path.write_text(html_text, encoding="utf-8")
    dist_index_path.write_text(html_text, encoding="utf-8")

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
                "site_index": str(site_index_path),
                "dist_index": str(dist_index_path),
                "history_json": str(history_path),
                "summary_json": str(summary_copy_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
