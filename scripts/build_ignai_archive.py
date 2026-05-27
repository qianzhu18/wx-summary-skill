#!/usr/bin/env python3
"""Build an archive index page for IGN AI daily reports.

Generates a dark-themed index page listing all daily reports with links.

Usage:
  python build_ignai_archive.py --dist-dir /path/to/dist
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

BG = "#07080c"
BG2 = "#0d0e14"
PANEL = "#13141c"
INK = "#e4e4e7"
MUTED = "#71717a"
LINE = "#1e1f2e"
ACCENT = "#f97316"
ACCENT_DIM = "rgba(249, 115, 22, 0.15)"
SIGNAL = "#5da9ff"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--dist-dir", required=True, help="Path to dist directory")
    p.add_argument("--group-name", default="IGN AI | 洋来")
    p.add_argument("--output", "-o", help="Output HTML path")
    return p.parse_args()


def get_daily_reports(dist_dir: Path) -> list[dict]:
    """Find all daily report files and extract metadata."""
    reports = []
    for f in sorted(dist_dir.glob("ignai-daily-*.html"), reverse=True):
        date_str = f.stem.replace("ignai-daily-", "")
        # Try to read basic stats from the file
        try:
            content = f.read_text(encoding="utf-8")
            # Extract message count from the HTML
            import re
            msg_match = re.search(r'<span class="stat-value accent">(\d+)</span>', content)
            sender_match = re.search(r'<span class="stat-value signal">(\d+)</span>', content)
            headline_match = re.search(r'<h1>(.*?)</h1>', content)

            msg_count = int(msg_match.group(1)) if msg_match else 0
            sender_count = int(sender_match.group(1)) if sender_match else 0
            headline = headline_match.group(1) if headline_match else f"{date_str} 群聊精华"
        except Exception:
            msg_count = 0
            sender_count = 0
            headline = f"{date_str} 群聊精华"

        reports.append({
            "date": date_str,
            "filename": f.name,
            "messages": msg_count,
            "senders": sender_count,
            "headline": headline,
        })

    return reports


def render_archive_html(reports: list[dict], group_name: str) -> str:
    """Render the archive index page."""
    cards = ""
    for r in reports:
        # Determine weekday
        from datetime import date
        d = date.fromisoformat(r["date"])
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday = weekday_names[d.weekday()]

        cards += f"""
      <a href="./{r['filename']}" class="report-card">
        <div class="report-date">
          <span class="date-day">{d.day}</span>
          <span class="date-month">{d.month}月</span>
        </div>
        <div class="report-info">
          <div class="report-weekday">{weekday}</div>
          <div class="report-headline">{r['headline']}</div>
          <div class="report-stats">
            <span>{r['messages']} 条消息</span>
            <span>{r['senders']} 人参与</span>
          </div>
        </div>
        <div class="report-arrow">→</div>
      </a>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{group_name} · 每日群聊精华档案</title>
  <meta name="theme-color" content="{BG}">
  <style>
    :root {{
      --bg: {BG};
      --bg2: {BG2};
      --panel: {PANEL};
      --ink: {INK};
      --muted: {MUTED};
      --line: {LINE};
      --accent: {ACCENT};
      --accent-dim: {ACCENT_DIM};
      --signal: {SIGNAL};
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--ink);
      font-family: "Noto Sans SC", -apple-system, "system-ui", sans-serif;
      line-height: 1.7;
      -webkit-font-smoothing: antialiased;
      min-height: 100vh;
    }}
    a {{ color: var(--accent); text-decoration: none; }}

    .header {{
      background: linear-gradient(180deg, {BG} 0%, {BG2} 100%);
      border-bottom: 1px solid var(--line);
      padding: 16px 24px;
      position: sticky;
      top: 0;
      z-index: 50;
      backdrop-filter: blur(12px);
    }}
    .header-inner {{
      max-width: 960px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
      font-weight: 700;
      font-size: 15px;
    }}
    .brand-logo {{
      width: 32px;
      height: 32px;
      border-radius: 8px;
      background: linear-gradient(135deg, {ACCENT}, {SIGNAL});
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 14px;
      color: #fff;
    }}
    .brand-accent {{ color: var(--accent); }}

    .hero {{
      padding: 56px 24px 40px;
      background: radial-gradient(ellipse 80% 50% at 50% -10%, rgba(249,115,22,0.08) 0%, transparent 70%);
      border-bottom: 1px solid var(--line);
    }}
    .hero-inner {{
      max-width: 960px;
      margin: 0 auto;
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: var(--accent);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      margin-bottom: 16px;
      padding: 4px 12px;
      border: 1px solid rgba(249,115,22,0.3);
      border-radius: 20px;
      background: var(--accent-dim);
    }}
    .hero h1 {{
      font-size: 36px;
      line-height: 1.15;
      font-weight: 800;
      letter-spacing: -0.02em;
      margin-bottom: 12px;
    }}
    .hero h1 em {{
      font-style: normal;
      color: var(--accent);
    }}
    .hero-sub {{
      color: var(--muted);
      font-size: 15px;
      max-width: 640px;
    }}
    .stats-row {{
      display: flex;
      gap: 32px;
      margin-top: 32px;
      padding-top: 28px;
      border-top: 1px solid var(--line);
    }}
    .stat-value {{
      font-size: 28px;
      font-weight: 800;
      letter-spacing: -0.02em;
      color: var(--ink);
    }}
    .stat-label {{
      font-size: 11px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}

    .container {{
      max-width: 960px;
      margin: 0 auto;
      padding: 48px 24px;
    }}
    .section-header {{
      display: flex;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 24px;
    }}
    .section-header h2 {{
      font-size: 20px;
      font-weight: 700;
    }}
    .section-header .badge {{
      font-size: 11px;
      color: var(--muted);
      background: var(--panel);
      border: 1px solid var(--line);
      padding: 2px 10px;
      border-radius: 20px;
    }}

    .report-list {{
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}
    .report-card {{
      display: flex;
      align-items: center;
      gap: 20px;
      padding: 16px 20px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      transition: border-color 0.2s, background 0.2s;
      color: var(--ink);
      text-decoration: none;
    }}
    .report-card:hover {{
      border-color: rgba(249,115,22,0.3);
      background: #1a1b26;
    }}
    .report-date {{
      display: flex;
      flex-direction: column;
      align-items: center;
      min-width: 48px;
    }}
    .date-day {{
      font-size: 24px;
      font-weight: 800;
      color: var(--accent);
      line-height: 1;
    }}
    .date-month {{
      font-size: 11px;
      color: var(--muted);
    }}
    .report-info {{
      flex: 1;
      min-width: 0;
    }}
    .report-weekday {{
      font-size: 11px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .report-headline {{
      font-size: 14px;
      font-weight: 600;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      margin: 2px 0;
    }}
    .report-stats {{
      font-size: 12px;
      color: var(--muted);
      display: flex;
      gap: 12px;
    }}
    .report-arrow {{
      color: var(--muted);
      font-size: 18px;
      transition: color 0.2s;
    }}
    .report-card:hover .report-arrow {{
      color: var(--accent);
    }}

    .footer {{
      max-width: 960px;
      margin: 0 auto;
      padding: 32px 24px;
      text-align: center;
      color: #52525b;
      font-size: 12px;
    }}

    @media (max-width: 640px) {{
      .hero h1 {{ font-size: 24px; }}
      .stats-row {{ gap: 20px; flex-wrap: wrap; }}
      .stat-value {{ font-size: 22px; }}
      .report-card {{ padding: 12px 16px; gap: 12px; }}
      .date-day {{ font-size: 20px; }}
    }}
  </style>
</head>
<body>
  <header class="header">
    <div class="header-inner">
      <div class="brand">
        <div class="brand-logo">I</div>
        <span>IGN AI <span class="brand-accent">社区</span></span>
      </div>
    </div>
  </header>

  <div class="hero">
    <div class="hero-inner">
      <div class="eyebrow">每日群聊精华档案</div>
      <h1>群聊<em>日报</em>档案</h1>
      <p class="hero-sub">{group_name} 的每日群聊精华，自动从群聊记录中提取热点话题、活跃成员和精彩语录</p>
      <div class="stats-row">
        <div>
          <div class="stat-value">{len(reports)}</div>
          <div class="stat-label">日报期数</div>
        </div>
        <div>
          <div class="stat-value">{reports[0]['date'] if reports else 'N/A'}</div>
          <div class="stat-label">最新一期</div>
        </div>
        <div>
          <div class="stat-value">{reports[-1]['date'] if reports else 'N/A'}</div>
          <div class="stat-label">最早一期</div>
        </div>
      </div>
    </div>
  </div>

  <div class="container">
    <div class="section-header">
      <h2>全部日报</h2>
      <span class="badge">{len(reports)} 期</span>
    </div>
    <div class="report-list">
{cards}
    </div>
  </div>

  <div class="footer">
    <p>{group_name} · 每日群聊精华档案</p>
    <p style="margin-top:8px">由 IGN AI 社区自动生成 · {datetime.now().strftime('%Y-%m-%d')}</p>
  </div>
</body>
</html>"""


def main() -> None:
    args = parse_args()
    dist_dir = Path(args.dist_dir).expanduser().resolve()

    if not dist_dir.exists():
        print(f"Error: dist directory not found at {dist_dir}")
        return

    reports = get_daily_reports(dist_dir)
    print(f"Found {len(reports)} daily reports")

    html = render_archive_html(reports, args.group_name)

    if args.output:
        out_path = Path(args.output).expanduser().resolve()
    else:
        out_path = dist_dir / "index.html"

    out_path.write_text(html, encoding="utf-8")
    print(f"Archive index: {out_path}")


if __name__ == "__main__":
    main()
