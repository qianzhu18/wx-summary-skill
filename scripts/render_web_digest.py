#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a local WeChat web digest.")
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


def markdown_report(summary: dict[str, Any], analysis: dict[str, Any]) -> str:
    verdict = period_verdict(summary)
    lines = [
        f"{summary['group_name']} 群聊信息报 · {summary['time_range']}",
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
    for idx, item in enumerate(analysis["top_senders"][:10], start=1):
        lines.append(f"{idx}. {item['name']}：{item['count']}")

    lines.extend(["", summary["opening"], "", "核心热点", ""])
    for idx, thread in enumerate(summary.get("main_threads", []), start=1):
        lines.append(f"{idx}. {thread['title']}")
        lines.append(f"   {thread['summary']}")
        lines.append("")

    if summary.get("people"):
        lines.append("值得记住的人")
        lines.append("")
        for person in summary["people"]:
            lines.append(f"- {person['name']}｜{person['tag']}")
            lines.append(f"  {person['desc']}")
        lines.append("")

    if summary.get("timeline"):
        lines.append("时间切片")
        lines.append("")
        for item in summary["timeline"]:
            lines.append(f"- {item['date']} {item['label']}")
            for bullet in item.get("bullets", []):
                lines.append(f"  - {bullet}")
        lines.append("")

    if summary.get("quotes"):
        lines.append("原话")
        lines.append("")
        for quote in summary["quotes"]:
            lines.append(f"- “{quote['text']}” —— {quote['who']}")
        lines.append("")

    if verdict:
        lines.extend(["一句话判断", "", verdict, ""])

    if summary.get("links"):
        lines.append("关联链接 / 资源")
        lines.append("")
        for item in summary["links"]:
            lines.append(f"- {item['title']}：{item['note']}")
        lines.append("")

    if summary.get("next_actions"):
        lines.append("后续可跟进")
        lines.append("")
        for item in summary["next_actions"]:
            lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_list(items: list[str]) -> str:
    return "".join(f"<li>{html.escape(item)}</li>" for item in items)


def render_html(summary: dict[str, Any], analysis: dict[str, Any]) -> str:
    generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    verdict = period_verdict(summary)
    people_html = "".join(
        (
            '<article class="person-item">'
            f"<h3>{html.escape(person['name'])}</h3>"
            f"<div class=\"meta\">{html.escape(person['tag'])}</div>"
            f"<p>{html.escape(person['desc'])}</p>"
            "</article>"
        )
        for person in summary.get("people", [])
    )
    threads_html = "".join(
        (
            '<article class="thread-item">'
            f"<h3>{html.escape(thread['title'])}</h3>"
            f"<p>{html.escape(thread['summary'])}</p>"
            "</article>"
        )
        for thread in summary.get("main_threads", [])
    )
    timeline_html = "".join(
        (
            '<article class="timeline-day">'
            f"<h3>{html.escape(item['date'])} <span>{html.escape(item['label'])}</span></h3>"
            f"<ul>{render_list(item.get('bullets', []))}</ul>"
            "</article>"
        )
        for item in summary.get("timeline", [])
    )
    quotes_html = "".join(
        (
            "<blockquote>"
            f"<p>{html.escape(quote['text'])}</p>"
            f"<footer>{html.escape(quote['who'])}</footer>"
            "</blockquote>"
        )
        for quote in summary.get("quotes", [])
    )
    links_html = "".join(
        (
            '<article class="link-item">'
            f"<h3>{html.escape(item['title'])}</h3>"
            f"<p>{html.escape(item['note'])}</p>"
            "</article>"
        )
        for item in summary.get("links", [])
    )
    next_actions_html = "".join(
        f"<li>{html.escape(item)}</li>" for item in summary.get("next_actions", [])
    )
    top_senders_html = "".join(
        f"<li><span>{html.escape(item['name'])}</span><strong>{item['count']}</strong></li>"
        for item in analysis.get("top_senders", [])[:10]
    )
    stats_html = (
        f"<li><span>总消息数</span><strong>{analysis['total_messages']}</strong></li>"
        f"<li><span>参与人数</span><strong>{analysis['active_senders']}</strong></li>"
        f"<li><span>总字符数</span><strong>{analysis['char_count']}</strong></li>"
        f"<li><span>高峰日</span><strong>{html.escape(peak_day_label(analysis))}</strong></li>"
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(summary['group_name'])} - 群聊信息报</title>
  <style>
    :root {{
      --bg: #f5f3ee;
      --panel: #fbfaf7;
      --ink: #1b1b1b;
      --muted: #666153;
      --line: #d8d1c2;
      --accent: #8f2f25;
      --shadow: 0 14px 36px rgba(24, 22, 18, 0.08);
      --max: 1120px;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Noto Sans SC", "Helvetica Neue", sans-serif;
      color: var(--ink);
      background: var(--bg);
      line-height: 1.65;
    }}

    section {{
      width: 100%;
    }}

    .wrap {{
      width: min(calc(100% - 32px), var(--max));
      margin: 0 auto;
    }}

    .hero {{
      padding: 56px 0 40px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, #f8f5ef 0%, #f5f3ee 100%);
    }}

    .hero .eyebrow {{
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 12px;
    }}

    .hero h1 {{
      margin: 0;
      font-size: 42px;
      line-height: 1.15;
      letter-spacing: 0;
      max-width: 10em;
    }}

    .hero .subheadline {{
      margin: 16px 0 0;
      max-width: 760px;
      font-size: 20px;
      color: #2d2a24;
    }}

    .hero .opening {{
      margin-top: 22px;
      max-width: 760px;
      color: var(--muted);
      font-size: 16px;
    }}

    .hero-meta {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-top: 28px;
      padding: 0;
      list-style: none;
    }}

    .hero-meta li,
    .stats li,
    .leaders li {{
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      border-radius: 8px;
      padding: 14px 16px;
    }}

    .hero-meta span,
    .stats span,
    .leaders span {{
      display: block;
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 6px;
    }}

    .hero-meta strong,
    .stats strong,
    .leaders strong {{
      font-size: 18px;
    }}

    .summary-band {{
      padding: 22px 0;
      border-bottom: 1px solid var(--line);
    }}

    .summary-band p {{
      margin: 0;
      font-size: 18px;
      font-weight: 600;
    }}

    .section-block {{
      padding: 36px 0;
      border-bottom: 1px solid var(--line);
    }}

    .section-block h2 {{
      margin: 0 0 18px;
      font-size: 22px;
      letter-spacing: 0;
    }}

    .grid-two {{
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 28px;
      align-items: start;
    }}

    .thread-list,
    .people-list,
    .timeline-list,
    .links-list,
    .quotes-list {{
      display: grid;
      gap: 14px;
    }}

    .thread-item,
    .person-item,
    .timeline-day,
    .link-item,
    .quotes-list blockquote {{
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      border-radius: 8px;
      padding: 18px;
      margin: 0;
    }}

    .thread-item h3,
    .person-item h3,
    .timeline-day h3,
    .link-item h3 {{
      margin: 0 0 10px;
      font-size: 18px;
    }}

    .timeline-day h3 span {{
      color: var(--muted);
      font-size: 14px;
      font-weight: 500;
      margin-left: 6px;
    }}

    .person-item .meta {{
      color: var(--accent);
      font-size: 13px;
      font-weight: 700;
      margin-bottom: 10px;
    }}

    .thread-item p,
    .person-item p,
    .link-item p,
    .quotes-list p {{
      margin: 0;
      color: #2c2a26;
    }}

    .timeline-day ul,
    .next-actions ul {{
      margin: 0;
      padding-left: 18px;
    }}

    .quotes-list blockquote footer {{
      margin-top: 10px;
      color: var(--muted);
      font-size: 14px;
    }}

    .side-panel {{
      display: grid;
      gap: 14px;
    }}

    .stats,
    .leaders {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 12px;
    }}

    .leaders li {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
    }}

    .next-actions {{
      background: #eee4df;
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      padding: 32px 0;
    }}

    .next-actions h2 {{
      margin: 0 0 14px;
      font-size: 22px;
    }}

    footer {{
      padding: 20px 0 48px;
      color: var(--muted);
      font-size: 13px;
    }}

    @media (max-width: 920px) {{
      .hero h1 {{
        font-size: 34px;
      }}

      .hero .subheadline {{
        font-size: 18px;
      }}

      .grid-two,
      .hero-meta {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="wrap">
        <div class="eyebrow">群聊信息报 / Chat Digest</div>
        <h1>{html.escape(summary['headline'])}</h1>
        <p class="subheadline">{html.escape(summary['subheadline'])}</p>
        <p class="opening">{html.escape(summary['opening'])}</p>
        <ul class="hero-meta">
          <li><span>群聊</span><strong>{html.escape(summary['group_name'])}</strong></li>
          <li><span>时间范围</span><strong>{html.escape(summary['time_range'])}</strong></li>
          <li><span>生成时间</span><strong>{html.escape(generated_at)}</strong></li>
          <li><span>一句话判断</span><strong>{html.escape(verdict)}</strong></li>
        </ul>
      </div>
    </section>

    <section class="summary-band">
      <div class="wrap">
        <p>{html.escape(verdict)}</p>
      </div>
    </section>

    <section class="section-block">
      <div class="wrap grid-two">
        <div>
          <h2>核心热点</h2>
          <div class="thread-list">{threads_html}</div>
        </div>
        <aside class="side-panel">
          <div>
            <h2>消息统计</h2>
            <ul class="stats">{stats_html}</ul>
          </div>
          <div>
            <h2>活跃成员</h2>
            <ul class="leaders">{top_senders_html}</ul>
          </div>
        </aside>
      </div>
    </section>

    <section class="section-block">
      <div class="wrap">
        <h2>值得记住的人</h2>
        <div class="people-list">{people_html}</div>
      </div>
    </section>

    <section class="section-block">
      <div class="wrap">
        <h2>时间切片</h2>
        <div class="timeline-list">{timeline_html}</div>
      </div>
    </section>

    <section class="section-block">
      <div class="wrap grid-two">
        <div>
          <h2>原话</h2>
          <div class="quotes-list">{quotes_html}</div>
        </div>
        <div>
          <h2>关联链接 / 资源</h2>
          <div class="links-list">{links_html}</div>
        </div>
      </div>
    </section>

    <section class="next-actions">
      <div class="wrap">
        <h2>后续可跟进</h2>
        <ul>{next_actions_html}</ul>
      </div>
    </section>
  </main>

  <footer>
    <div class="wrap">
      基于真实微信群消息生成。本地保留分析文件、history 和静态 HTML，方便继续复查或复用。
    </div>
  </footer>
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
