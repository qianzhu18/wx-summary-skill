#!/usr/bin/env python3
"""Render IGN AI community-style dark-theme daily report.

Generates a self-contained HTML page matching qianzhu.online community aesthetic:
  - Dark background (#07080c)
  - Orange accent (#f97316) + blue signal (#5da9ff)
  - Noto Sans SC font
  - Sections: 群聊总结 → 热点 → 需求与链接人 → 资源 → 活跃之星 → 词云

Usage:
  python render_ignai_daily.py --summary summary.json --analysis analysis.json
  python render_ignai_daily.py --analysis analysis.json  # auto-generates summary
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Color palette (matches qianzhu.online community) ──────────────────────
BG = "#07080c"
BG2 = "#0d0e14"
PANEL = "#13141c"
PANEL_HOVER = "#1a1b26"
INK = "#e4e4e7"
MUTED = "#71717a"
MUTED2 = "#52525b"
LINE = "#1e1f2e"
ACCENT = "#f97316"
ACCENT_DIM = "rgba(249, 115, 22, 0.15)"
ACCENT_HOVER = "#fb923c"
SIGNAL = "#5da9ff"
SIGNAL_DIM = "rgba(93, 169, 255, 0.15)"
MAX_W = "960px"
RADIUS = "12px"


def e(text: str) -> str:
    return html_mod.escape(str(text))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Render IGN AI community daily report")
    p.add_argument("--summary", help="Path to summary.json")
    p.add_argument("--analysis", required=True, help="Path to analysis.json")
    p.add_argument("--output", "-o", help="Output HTML path (default: dist/ignai-daily.html)")
    p.add_argument("--logo", help="Path to community logo image (base64 embedded)")
    return p.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def auto_summary(analysis: dict[str, Any]) -> dict[str, Any]:
    """Generate a minimal summary from analysis data when summary.json is missing."""
    grp = analysis.get("group_name", "IGN AI")
    dr = analysis.get("date_range", {})
    since = dr.get("since", "")
    until = dr.get("until", "")
    time_range = f"{since} ~ {until}" if since != until else since

    top = analysis.get("top_senders", [])
    top_names = [t.get("name", "") for t in top[:5]]

    kw = analysis.get("keyword_hits", [])
    kw_str = "、".join(k.get("keyword", "") for k in kw[:5]) if kw else "AI工具"

    return {
        "group_name": grp,
        "group_id": analysis.get("group_id", ""),
        "time_range": time_range,
        "headline": f"{since} 群聊精华：{kw_str} 成焦点",
        "subheadline": f"当日共 {analysis.get('total_messages', 0)} 条消息，{analysis.get('active_senders', 0)} 人参与讨论",
        "opening": f"{grp} 在 {time_range} 内产生了 {analysis.get('total_messages', 0)} 条消息，{analysis.get('active_senders', 0)} 位成员参与。讨论围绕 {kw_str} 等话题展开。",
        "main_threads": [],
        "people": [],
        "timeline": [],
        "quotes": [],
        "links": [],
        "next_actions": [],
    }


# ── Content extraction helpers ────────────────────────────────────────────

def extract_hot_topics(analysis: dict[str, Any], summary: dict[str, Any]) -> list[dict]:
    """Extract hot topics from keyword hits and main threads."""
    topics = []
    kw_hits = analysis.get("keyword_hits", [])
    threads = summary.get("main_threads", [])

    # From keyword hits
    for kw in kw_hits[:8]:
        keyword = kw.get("keyword", "")
        count = kw.get("count", 0)
        # Find matching thread
        matched_thread = None
        for t in threads:
            if keyword.lower() in t.get("title", "").lower() or keyword.lower() in t.get("summary", "").lower():
                matched_thread = t
                break
        topics.append({
            "keyword": keyword,
            "count": count,
            "title": matched_thread["title"] if matched_thread else f"{keyword} 相关讨论",
            "summary": matched_thread["summary"] if matched_thread else f"群内围绕 {keyword} 的讨论共出现 {count} 次",
            "insight": "",
        })

    # Fill remaining from threads if needed
    if len(topics) < 4:
        for t in threads:
            if len(topics) >= 6:
                break
            title = t.get("title", "")
            if not any(title.lower().count(tp["keyword"].lower()) for tp in topics):
                topics.append({
                    "keyword": title[:6],
                    "count": 0,
                    "title": title,
                    "summary": t.get("summary", ""),
                    "insight": "",
                })

    return topics[:6]


def extract_needs(analysis: dict[str, Any], summary: dict[str, Any]) -> list[dict]:
    """Extract user needs and potential connectors."""
    needs = []
    quotes = summary.get("quotes", [])
    briefing = analysis.get("briefing", "")

    # Look for demand/help signals in quotes
    need_keywords = ["需求", "求助", "怎么", "哪里", "有没有", "推荐", "找", "帮", "需要", "问题"]
    for q in quotes:
        text = q.get("text", "")
        who = q.get("who", "")
        if any(kw in text for kw in need_keywords):
            needs.append({
                "text": text[:120],
                "from": who,
                "connector": "",
            })

    # From demand data if available
    demand_data = analysis.get("demand_signals", [])
    for d in demand_data[:3]:
        needs.append({
            "text": d.get("text", d.get("demand", ""))[:120],
            "from": d.get("from", ""),
            "connector": d.get("connector", ""),
        })

    return needs[:5]


def extract_resources(summary: dict[str, Any], analysis: dict[str, Any]) -> list[dict]:
    """Extract shared links and resources."""
    resources = []
    links = summary.get("links", [])
    freq_links = analysis.get("frequent_links", [])

    for link in links:
        resources.append({
            "title": link.get("title", ""),
            "url": link.get("url", ""),
            "note": link.get("note", ""),
        })

    for fl in freq_links:
        title = fl.get("title", fl.get("url", ""))
        if not any(title in r["title"] for r in resources):
            resources.append({
                "title": title,
                "url": fl.get("url", ""),
                "note": f"被提及 {fl.get('count', 1)} 次",
            })

    return resources[:8]


def extract_active_stars(analysis: dict[str, Any]) -> list[dict]:
    """Extract top active members with stats."""
    stars = []
    top_senders = analysis.get("top_senders", [])
    for ts in top_senders[:10]:
        name = ts.get("name", "未知")
        count = ts.get("count", 0)
        stars.append({
            "name": name,
            "count": count,
            "initial": name[0] if name else "?",
        })
    return stars


def extract_word_cloud(analysis: dict[str, Any]) -> list[dict]:
    """Extract keyword frequencies for word cloud visualization."""
    words = []
    kw_hits = analysis.get("keyword_hits", [])
    for kw in kw_hits[:20]:
        words.append({
            "word": kw.get("keyword", ""),
            "count": kw.get("count", 1),
        })

    # Normalize weights for visual sizing
    if words:
        max_count = max(w["count"] for w in words)
        for w in words:
            w["weight"] = max(0.5, w["count"] / max_count)

    return words


def extract_quotes(summary: dict[str, Any], analysis: dict[str, Any]) -> list[dict]:
    """Extract notable quotes."""
    quotes = []
    for q in summary.get("quotes", []):
        text = q.get("text", "")
        if len(text) > 10 and not text.startswith("wxid_"):
            quotes.append({
                "text": text[:150],
                "who": q.get("who", ""),
            })

    # From quote candidates
    qc = analysis.get("quote_candidates", [])
    for q in qc:
        text = q.get("text", q.get("content", ""))
        if len(text) > 10 and not text.startswith("wxid_"):
            if not any(text[:30] in eq["text"] for eq in quotes):
                quotes.append({
                    "text": text[:150],
                    "who": q.get("sender", q.get("who", "")),
                })

    return quotes[:6]


# ── HTML rendering ────────────────────────────────────────────────────────

def render_css() -> str:
    return f"""
:root {{
  --bg: {BG};
  --bg2: {BG2};
  --panel: {PANEL};
  --panel-hover: {PANEL_HOVER};
  --ink: {INK};
  --muted: {MUTED};
  --muted2: {MUTED2};
  --line: {LINE};
  --accent: {ACCENT};
  --accent-dim: {ACCENT_DIM};
  --accent-hover: {ACCENT_HOVER};
  --signal: {SIGNAL};
  --signal-dim: {SIGNAL_DIM};
  --max: {MAX_W};
  --radius: {RADIUS};
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: var(--bg);
  color: var(--ink);
  font-family: "Noto Sans SC", -apple-system, "system-ui", "Segoe UI", sans-serif;
  line-height: 1.7;
  -webkit-font-smoothing: antialiased;
  min-height: 100vh;
}}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ color: var(--accent-hover); }}

/* ── Header ─────────────────────────────────────────────── */
.header {{
  background: linear-gradient(180deg, {BG} 0%, {BG2} 100%);
  border-bottom: 1px solid var(--line);
  padding: 0;
  position: sticky;
  top: 0;
  z-index: 50;
  backdrop-filter: blur(12px);
}}
.header-inner {{
  max-width: var(--max);
  margin: 0 auto;
  padding: 16px 24px;
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
  object-fit: cover;
}}
.brand-accent {{ color: var(--accent); }}
.header-meta {{
  font-size: 12px;
  color: var(--muted);
  display: flex;
  align-items: center;
  gap: 16px;
}}
.header-meta .dot {{
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  display: inline-block;
}}

/* ── Hero ────────────────────────────────────────────────── */
.hero {{
  padding: 56px 24px 40px;
  background: radial-gradient(ellipse 80% 50% at 50% -10%, rgba(249,115,22,0.08) 0%, transparent 70%);
  border-bottom: 1px solid var(--line);
}}
.hero-inner {{
  max-width: var(--max);
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
  line-height: 1.7;
}}

/* ── Stats row ──────────────────────────────────────────── */
.stats-row {{
  display: flex;
  gap: 32px;
  margin-top: 32px;
  padding-top: 28px;
  border-top: 1px solid var(--line);
  flex-wrap: wrap;
}}
.stat {{
  display: flex;
  flex-direction: column;
  gap: 4px;
}}
.stat-value {{
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--ink);
}}
.stat-value.accent {{ color: var(--accent); }}
.stat-value.signal {{ color: var(--signal); }}
.stat-label {{
  font-size: 11px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}}

/* ── Section ────────────────────────────────────────────── */
.section {{
  max-width: var(--max);
  margin: 0 auto;
  padding: 48px 24px;
  border-bottom: 1px solid var(--line);
}}
.section:last-child {{ border-bottom: none; }}
.section-header {{
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 24px;
}}
.section-header h2 {{
  font-size: 20px;
  font-weight: 700;
  color: var(--ink);
}}
.section-header .badge {{
  font-size: 11px;
  color: var(--muted);
  background: var(--panel);
  border: 1px solid var(--line);
  padding: 2px 10px;
  border-radius: 20px;
}}
.section-desc {{
  color: var(--muted);
  font-size: 14px;
  margin-bottom: 24px;
  max-width: 640px;
}}

/* ── Cards ──────────────────────────────────────────────── */
.card-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}}
.card {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 20px;
  transition: border-color 0.2s, background 0.2s;
}}
.card:hover {{
  border-color: rgba(249,115,22,0.3);
  background: var(--panel-hover);
}}
.card-title {{
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 8px;
  color: var(--ink);
  display: flex;
  align-items: center;
  gap: 8px;
}}
.card-title .keyword-tag {{
  font-size: 11px;
  color: var(--accent);
  background: var(--accent-dim);
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: 600;
}}
.card-body {{
  font-size: 13px;
  color: var(--muted);
  line-height: 1.7;
}}
.card-body .quote {{
  border-left: 2px solid var(--accent);
  padding-left: 12px;
  margin-top: 8px;
  font-style: italic;
  color: var(--ink);
  font-size: 13px;
}}

/* ── Hot topics ─────────────────────────────────────────── */
.topic-card {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 24px;
  transition: border-color 0.2s;
}}
.topic-card:hover {{
  border-color: rgba(249,115,22,0.3);
}}
.topic-header {{
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}}
.topic-keyword {{
  font-size: 12px;
  font-weight: 700;
  color: var(--accent);
  background: var(--accent-dim);
  padding: 3px 10px;
  border-radius: 16px;
  white-space: nowrap;
}}
.topic-count {{
  font-size: 11px;
  color: var(--muted);
}}
.topic-title {{
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 8px;
  color: var(--ink);
}}
.topic-summary {{
  font-size: 13px;
  color: var(--muted);
  line-height: 1.7;
}}
.topic-quote {{
  margin-top: 12px;
  border-left: 2px solid var(--signal);
  padding-left: 12px;
  font-size: 13px;
  color: var(--ink);
  font-style: italic;
}}
.topic-quote .attribution {{
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: var(--muted);
  font-style: normal;
}}

/* ── Needs & connectors ─────────────────────────────────── */
.need-item {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 20px;
  display: flex;
  gap: 16px;
  align-items: flex-start;
}}
.need-icon {{
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--signal-dim);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
}}
.need-content {{
  flex: 1;
}}
.need-text {{
  font-size: 14px;
  color: var(--ink);
  line-height: 1.6;
  margin-bottom: 8px;
}}
.need-meta {{
  font-size: 12px;
  color: var(--muted);
  display: flex;
  gap: 16px;
}}
.need-meta .connector {{
  color: var(--signal);
}}

/* ── Resource list ──────────────────────────────────────── */
.resource-item {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  transition: border-color 0.2s;
}}
.resource-item:hover {{
  border-color: rgba(249,115,22,0.3);
}}
.resource-icon {{
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--accent-dim);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
}}
.resource-info {{
  flex: 1;
  min-width: 0;
}}
.resource-title {{
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.resource-note {{
  font-size: 12px;
  color: var(--muted);
}}

/* ── Active stars ───────────────────────────────────────── */
.stars-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}}
.star-card {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  transition: border-color 0.2s;
}}
.star-card:hover {{
  border-color: rgba(249,115,22,0.3);
}}
.star-avatar {{
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent-dim), var(--signal-dim));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
  color: var(--accent);
  flex-shrink: 0;
}}
.star-info {{
  flex: 1;
  min-width: 0;
}}
.star-name {{
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.star-count {{
  font-size: 11px;
  color: var(--muted);
}}
.star-bar {{
  height: 3px;
  background: var(--line);
  border-radius: 2px;
  margin-top: 6px;
  overflow: hidden;
}}
.star-bar-fill {{
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--accent), var(--signal));
}}

/* ── Word cloud ─────────────────────────────────────────── */
.wordcloud {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: center;
  padding: 24px;
}}
.word-tag {{
  display: inline-block;
  padding: 6px 14px;
  border-radius: 20px;
  font-weight: 600;
  white-space: nowrap;
  transition: transform 0.2s;
}}
.word-tag:hover {{
  transform: scale(1.05);
}}

/* ── Quotes wall ────────────────────────────────────────── */
.quote-wall {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}}
.quote-card {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 20px;
  position: relative;
}}
.quote-card::before {{
  content: "“";
  position: absolute;
  top: 12px;
  left: 16px;
  font-size: 48px;
  color: var(--accent);
  opacity: 0.2;
  font-family: Georgia, serif;
  line-height: 1;
}}
.quote-text {{
  font-size: 14px;
  color: var(--ink);
  line-height: 1.7;
  padding-left: 24px;
  margin-bottom: 12px;
}}
.quote-author {{
  font-size: 12px;
  color: var(--muted);
  padding-left: 24px;
}}

/* ── Footer ─────────────────────────────────────────────── */
.footer {{
  max-width: var(--max);
  margin: 0 auto;
  padding: 32px 24px;
  text-align: center;
  color: var(--muted2);
  font-size: 12px;
}}
.footer a {{ color: var(--muted); }}

/* ── Responsive ─────────────────────────────────────────── */
@media (max-width: 640px) {{
  .hero h1 {{ font-size: 24px; }}
  .stats-row {{ gap: 20px; }}
  .stat-value {{ font-size: 22px; }}
  .card-grid {{ grid-template-columns: 1fr; }}
  .stars-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .quote-wall {{ grid-template-columns: 1fr; }}
}}
"""


def render_hero(summary: dict, analysis: dict) -> str:
    total = analysis.get("total_messages", 0)
    senders = analysis.get("active_senders", 0)
    chars = analysis.get("char_count", 0)
    peak_hour = analysis.get("peak_hour", {})
    peak_h = peak_hour.get("hour", "")
    peak_c = peak_hour.get("count", "")

    headline = summary.get("headline", f"{summary.get('time_range', '')} 群聊精华")
    subheadline = summary.get("subheadline", summary.get("opening", ""))
    time_range = summary.get("time_range", "")
    group_name = summary.get("group_name", "IGN AI")

    return f"""
<div class="hero">
  <div class="hero-inner">
    <div class="eyebrow"><span class="dot" style="width:6px;height:6px;border-radius:50%;background:{ACCENT};display:inline-block"></span> {e(group_name)} · 每日群聊精华</div>
    <h1>{e(headline)}</h1>
    <p class="hero-sub">{e(subheadline)}</p>
    <div class="stats-row">
      <div class="stat">
        <span class="stat-value accent">{total}</span>
        <span class="stat-label">消息总数</span>
      </div>
      <div class="stat">
        <span class="stat-value signal">{senders}</span>
        <span class="stat-label">参与人数</span>
      </div>
      <div class="stat">
        <span class="stat-value">{chars:,}</span>
        <span class="stat-label">总字符数</span>
      </div>
      <div class="stat">
        <span class="stat-value">{peak_h}:00</span>
        <span class="stat-label">高峰时段 ({peak_c}条)</span>
      </div>
      <div class="stat">
        <span class="stat-value">{e(time_range)}</span>
        <span class="stat-label">日期</span>
      </div>
    </div>
  </div>
</div>"""


def render_hot_topics(topics: list[dict]) -> str:
    if not topics:
        return ""

    cards = ""
    for t in topics:
        quote_html = ""
        if t.get("insight"):
            quote_html = f'<div class="topic-quote">{e(t["insight"])}</div>'
        cards += f"""
    <div class="topic-card">
      <div class="topic-header">
        <span class="topic-keyword">#{e(t["keyword"])}</span>
        <span class="topic-count">{t["count"]} 次提及</span>
      </div>
      <div class="topic-title">{e(t["title"])}</div>
      <div class="topic-summary">{e(t["summary"])}</div>
      {quote_html}
    </div>"""

    return f"""
<div class="section">
  <div class="section-header">
    <h2>热点话题</h2>
    <span class="badge">{len(topics)} 个</span>
  </div>
  <p class="section-desc">群内讨论最集中的关键词和话题，按提及次数排列</p>
  <div class="card-grid">{cards}
  </div>
</div>"""


def render_needs(needs: list[dict]) -> str:
    if not needs:
        return ""

    items = ""
    for n in needs:
        connector_html = ""
        if n.get("connector"):
            connector_html = f'<span class="connector">→ {e(n["connector"])}</span>'
        items += f"""
    <div class="need-item">
      <div class="need-icon">?</div>
      <div class="need-content">
        <div class="need-text">{e(n["text"])}</div>
        <div class="need-meta">
          <span>来自: {e(n["from"])}</span>
          {connector_html}
        </div>
      </div>
    </div>"""

    return f"""
<div class="section">
  <div class="section-header">
    <h2>需求与链接人</h2>
    <span class="badge">{len(needs)} 条</span>
  </div>
  <p class="section-desc">从群聊中提取的用户需求和潜在的资源对接人</p>
  <div style="display:flex;flex-direction:column;gap:12px">{items}
  </div>
</div>"""


def render_resources(resources: list[dict]) -> str:
    if not resources:
        return ""

    items = ""
    for r in resources:
        title = r.get("title", "")
        url = r.get("url", "")
        note = r.get("note", "")
        title_html = f'<a href="{e(url)}" target="_blank">{e(title)}</a>' if url else e(title)
        items += f"""
    <div class="resource-item">
      <div class="resource-icon">🔗</div>
      <div class="resource-info">
        <div class="resource-title">{title_html}</div>
        <div class="resource-note">{e(note)}</div>
      </div>
    </div>"""

    return f"""
<div class="section">
  <div class="section-header">
    <h2>共享资源</h2>
    <span class="badge">{len(resources)} 个</span>
  </div>
  <p class="section-desc">群内分享的工具、文章和有价值的链接</p>
  <div style="display:flex;flex-direction:column;gap:10px">{items}
  </div>
</div>"""


def render_active_stars(stars: list[dict]) -> str:
    if not stars:
        return ""

    max_count = max(s["count"] for s in stars) if stars else 1
    cards = ""
    for i, s in enumerate(stars):
        pct = (s["count"] / max_count * 100) if max_count else 0
        # Gradient colors based on rank
        colors = [
            ("#f97316", "#fb923c"),  # orange
            ("#5da9ff", "#7cc8ff"),  # blue
            ("#a78bfa", "#c4b5fd"),  # purple
            ("#34d399", "#6ee7b7"),  # green
            ("#f472b6", "#f9a8d4"),  # pink
        ]
        c1, c2 = colors[i % len(colors)]
        cards += f"""
    <div class="star-card">
      <div class="star-avatar" style="background:linear-gradient(135deg,{c1}22,{c2}22);color:{c1}">{e(s["initial"])}</div>
      <div class="star-info">
        <div class="star-name">{e(s["name"])}</div>
        <div class="star-count">{s["count"]} 条消息</div>
        <div class="star-bar"><div class="star-bar-fill" style="width:{pct:.0f}%;background:linear-gradient(90deg,{c1},{c2})"></div></div>
      </div>
    </div>"""

    return f"""
<div class="section">
  <div class="section-header">
    <h2>活跃之星</h2>
    <span class="badge">Top {len(stars)}</span>
  </div>
  <p class="section-desc">当日发言最活跃的成员排行</p>
  <div class="stars-grid">{cards}
  </div>
</div>"""


def render_word_cloud(words: list[dict]) -> str:
    if not words:
        return ""

    tags = ""
    # Color palette for word cloud
    colors = [
        ("#f97316", "rgba(249,115,22,0.12)"),
        ("#5da9ff", "rgba(93,169,255,0.12)"),
        ("#a78bfa", "rgba(167,139,250,0.12)"),
        ("#34d399", "rgba(52,211,153,0.12)"),
        ("#f472b6", "rgba(244,114,182,0.12)"),
        ("#fbbf24", "rgba(251,191,36,0.12)"),
    ]

    for i, w in enumerate(words):
        weight = w.get("weight", 0.5)
        size = max(12, int(12 + weight * 16))
        fg, bg = colors[i % len(colors)]
        tags += f'<span class="word-tag" style="font-size:{size}px;color:{fg};background:{bg}">{e(w["word"])}</span>'

    return f"""
<div class="section">
  <div class="section-header">
    <h2>词云</h2>
    <span class="badge">{len(words)} 个关键词</span>
  </div>
  <p class="section-desc">群聊高频词汇可视化</p>
  <div class="wordcloud">{tags}
  </div>
</div>"""


def render_quotes_section(quotes: list[dict]) -> str:
    if not quotes:
        return ""

    cards = ""
    for q in quotes:
        cards += f"""
    <div class="quote-card">
      <div class="quote-text">{e(q["text"])}</div>
      <div class="quote-author">—— {e(q["who"])}</div>
    </div>"""

    return f"""
<div class="section">
  <div class="section-header">
    <h2>精选语录</h2>
    <span class="badge">{len(quotes)} 条</span>
  </div>
  <p class="section-desc">群成员的精彩观点和讨论片段</p>
  <div class="quote-wall">{cards}
  </div>
</div>"""


def render_footer(group_name: str, time_range: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""
<div class="footer">
  <p>{e(group_name)} · 每日群聊精华 · {e(time_range)}</p>
  <p style="margin-top:8px">由 IGN AI 社区自动生成 · {now}</p>
  <p style="margin-top:12px"><a href="https://qianzhu.online/community/">← 返回社区首页</a></p>
</div>"""


def render_full_html(
    summary: dict,
    analysis: dict,
    topics: list[dict],
    needs: list[dict],
    resources: list[dict],
    stars: list[dict],
    words: list[dict],
    quotes: list[dict],
    logo_data_uri: str = "",
) -> str:
    group_name = summary.get("group_name", "IGN AI")
    time_range = summary.get("time_range", "")
    title = f"{group_name} · {time_range} 每日群聊精华"

    logo_html = ""
    if logo_data_uri:
        logo_html = f'<img class="brand-logo" src="{logo_data_uri}" alt="logo">'
    else:
        logo_html = f'<div style="width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,{ACCENT},{SIGNAL});display:flex;align-items:center;justify-content:center;font-weight:800;font-size:14px;color:#fff">I</div>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{e(title)}</title>
  <meta name="theme-color" content="{BG}">
  <meta property="og:title" content="{e(title)}">
  <meta property="og:description" content="{e(summary.get('subheadline', ''))}">
  <meta property="og:type" content="article">
  <style>{render_css()}</style>
</head>
<body>
  <header class="header">
    <div class="header-inner">
      <div class="brand">
        {logo_html}
        <span>IGN AI <span class="brand-accent">社区</span></span>
      </div>
      <div class="header-meta">
        <span><span class="dot"></span> 每日群聊精华</span>
        <span>{e(time_range)}</span>
      </div>
    </div>
  </header>

  {render_hero(summary, analysis)}
  {render_hot_topics(topics)}
  {render_quotes_section(quotes)}
  {render_needs(needs)}
  {render_resources(resources)}
  {render_active_stars(stars)}
  {render_word_cloud(words)}
  {render_footer(group_name, time_range)}
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    analysis_path = Path(args.analysis).expanduser().resolve()
    analysis = read_json(analysis_path)

    if args.summary:
        summary_path = Path(args.summary).expanduser().resolve()
        summary = read_json(summary_path)
    else:
        summary = auto_summary(analysis)

    # Load logo if provided
    logo_data_uri = ""
    if args.logo:
        import base64
        logo_path = Path(args.logo).expanduser().resolve()
        if logo_path.exists():
            ext = logo_path.suffix.lower().lstrip(".")
            mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "svg": "image/svg+xml"}.get(ext, "image/png")
            data = logo_path.read_bytes()
            logo_data_uri = f"data:{mime};base64,{base64.b64encode(data).decode()}"

    # Extract all content sections
    topics = extract_hot_topics(analysis, summary)
    needs = extract_needs(analysis, summary)
    resources = extract_resources(summary, analysis)
    stars = extract_active_stars(analysis)
    words = extract_word_cloud(analysis)
    quotes = extract_quotes(summary, analysis)

    # Render HTML
    html_content = render_full_html(summary, analysis, topics, needs, resources, stars, words, quotes, logo_data_uri)

    # Determine output path
    if args.output:
        out_path = Path(args.output).expanduser().resolve()
    else:
        group_dir = analysis_path.parent.parent
        dr = analysis.get("date_range", {})
        date_str = dr.get("since", "unknown")
        out_path = group_dir / "dist" / f"ignai-daily-{date_str}.html"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_content, encoding="utf-8")
    print(json.dumps({
        "output": str(out_path),
        "sections": {
            "hot_topics": len(topics),
            "needs": len(needs),
            "resources": len(resources),
            "active_stars": len(stars),
            "word_cloud": len(words),
            "quotes": len(quotes),
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
