#!/usr/bin/env python3
"""Render IGN AI community-style dark-theme daily report.

Generates a self-contained HTML page matching qianzhu.online community aesthetic:
  - Dark background (#07080c)
  - Orange accent (#f97316) + blue signal (#5da9ff)
  - Noto Sans SC font
  - Sections: 群聊总结 → 热点 → 需求与链接人 → 资源 → 活跃之星 → 词云

Usage:
  python render_ignai_daily.py --analysis analysis.json --messages messages.json
  python render_ignai_daily.py --analysis analysis.json  # uses quote_candidates from analysis
"""

from __future__ import annotations

import argparse
import base64
import html as html_mod
import json
import re
from collections import Counter, defaultdict
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

# ── AI/Tech keywords for topic extraction ─────────────────────────────────
TOPIC_KEYWORDS = [
    "OpenAI", "Claude", "Gemini", "GPT", "API", "Agent", "token", "Codex",
    "Kimi", "DeepSeek", "Qwen", "通义", "千问", "Llama", "Mistral",
    "Cursor", "Copilot", "Windsurf", "Replit", "v0", "Bolt",
    "Midjourney", "SD", "Stable Diffusion", "DALL-E", "Sora",
    "LangChain", "Dify", "Coze", "扣子", "n8n",
    "模型", "大模型", "LLM", "RAG", "向量", "embedding",
    "部署", "服务器", "云", "阿里云", "腾讯云", "AWS",
    "黑客松", "hackathon", "比赛", "竞赛",
    "skill", "workflow", "自动化", "机器人",
    "Qwen3", "SkyClaw", "OpenClaw", "Prism",
]


def e(text: str) -> str:
    return html_mod.escape(str(text))


def clean_msg(text: str) -> str:
    """Clean message content for display."""
    if not text:
        return ""
    # Decode HTML entities first
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"')
    # Remove XML/image/location data
    if any(text.startswith(p) for p in ("<?xml", "wxid_", "<msg>", "<xml")):
        return ""
    if "<img aeskey=" in text or "<location " in text:
        return ""
    # Remove [Broken] markers
    text = re.sub(r"\[Broken\]", "", text)
    # Remove [动画表情] markers
    text = re.sub(r"\[动画表情\]", "", text)
    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Skip if too short after cleaning
    if len(text) < 10:
        return ""
    # Truncate if too long
    if len(text) > 200:
        text = text[:197] + "…"
    return text


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Render IGN AI community daily report")
    p.add_argument("--summary", help="Path to summary.json")
    p.add_argument("--analysis", required=True, help="Path to analysis.json")
    p.add_argument("--messages", help="Path to raw messages.json (for real quotes)")
    p.add_argument("--output", "-o", help="Output HTML path")
    p.add_argument("--logo", help="Path to community logo image")
    return p.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_messages(messages_path: str | None, analysis: dict, date_str: str) -> list[dict]:
    """Load messages from file or extract from analysis quote_candidates."""
    if messages_path:
        msgs = read_json(Path(messages_path))
        # Filter to target date
        return [m for m in msgs if m.get("time", "").startswith(date_str)]
    # Fallback: use quote_candidates from analysis
    return analysis.get("quote_candidates", [])


def extract_topics_from_messages(messages: list[dict], analysis: dict) -> list[dict]:
    """Extract hot topics with real quotes from messages."""
    # Group messages by keyword
    keyword_msgs: dict[str, list[dict]] = defaultdict(list)
    kw_hits = analysis.get("keyword_hits", [])
    known_keywords = {kw["keyword"] for kw in kw_hits}

    for msg in messages:
        content = msg.get("content", "") or msg.get("text", "")
        sender = msg.get("sender", msg.get("who", ""))
        time_str = msg.get("time", "")
        if not content or not sender:
            continue
        cleaned = clean_msg(content)
        if not cleaned or len(cleaned) < 15:
            continue
        content_lower = content.lower()
        for kw in known_keywords:
            if kw.lower() in content_lower:
                keyword_msgs[kw].append({
                    "text": cleaned,
                    "sender": sender,
                    "time": time_str,
                })

    # Assign unique quotes to each topic (no reuse)
    used_quotes: set[str] = set()
    topics = []

    for kw_hit in kw_hits[:6]:
        keyword = kw_hit["keyword"]
        count = kw_hit["count"]
        msgs_for_kw = keyword_msgs.get(keyword, [])

        # Pick best unused quotes
        good_quotes = [m for m in msgs_for_kw if m["text"][:30] not in used_quotes]
        good_quotes.sort(key=lambda m: len(m["text"]), reverse=True)

        if good_quotes:
            quote = good_quotes[0]
            used_quotes.add(quote["text"][:30])
            summary = f"来自 {quote['sender']} 的讨论"
            insight = quote["text"][:120]
            attribution = quote["sender"]
        else:
            summary = f"群内共 {count} 次提及"
            insight = ""
            attribution = ""

        topics.append({
            "keyword": keyword,
            "count": count,
            "title": f"{keyword} 相关讨论",
            "summary": summary,
            "insight": insight,
            "attribution": attribution,
            "quotes": good_quotes[:2],
        })

    return topics


def extract_topics_from_analysis(analysis: dict, summary: dict) -> list[dict]:
    """Fallback: extract topics from analysis data when no raw messages."""
    topics = []
    kw_hits = analysis.get("keyword_hits", [])
    quote_candidates = analysis.get("quote_candidates", [])

    for kw_hit in kw_hits[:6]:
        keyword = kw_hit["keyword"]
        count = kw_hit["count"]

        # Find relevant quotes
        relevant = []
        for q in quote_candidates:
            text = q.get("text", q.get("content", ""))
            if keyword.lower() in text.lower():
                cleaned = clean_msg(text)
                if cleaned and len(cleaned) > 15:
                    relevant.append({
                        "text": cleaned,
                        "sender": q.get("sender", q.get("who", "")),
                        "time": q.get("time", ""),
                    })

        if relevant:
            quote = relevant[0]
            insight = quote["text"][:120]
            attribution = quote["sender"]
        else:
            insight = ""
            attribution = ""

        topics.append({
            "keyword": keyword,
            "count": count,
            "title": f"{keyword} 相关讨论",
            "summary": f"群内共 {count} 次提及",
            "insight": insight,
            "attribution": attribution,
            "quotes": relevant[:2],
        })

    return topics


def extract_needs_from_messages(messages: list[dict]) -> list[dict]:
    """Extract user needs from real messages."""
    need_keywords = ["需求", "求助", "怎么", "哪里", "有没有", "推荐", "找", "帮", "需要", "问题", "想要", "求", "有吗"]
    needs = []

    for msg in messages:
        content = msg.get("content", "") or msg.get("text", "")
        sender = msg.get("sender", msg.get("who", ""))
        if not content or not sender:
            continue

        cleaned = clean_msg(content)
        if not cleaned or len(cleaned) < 10:
            continue

        # Check if it's a need/help request
        if any(kw in content for kw in need_keywords):
            # Skip bot responses
            if sender in ("管家",):
                continue
            needs.append({
                "text": cleaned[:120],
                "from": sender,
                "connector": "",
            })

    return needs[:5]


def extract_resources_from_messages(messages: list[dict]) -> list[dict]:
    """Extract shared links and resources from messages."""
    resources = []
    seen_urls = set()

    for msg in messages:
        content = msg.get("content", "") or msg.get("text", "")
        sender = msg.get("sender", msg.get("who", ""))
        if not content:
            continue

        # Extract URLs
        urls = re.findall(r'https?://[^\s<>"\']+', content)
        for url in urls:
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Try to extract title from surrounding text
            title = url[:80]
            # Look for text before the URL
            before = content[:content.index(url)].strip()
            if before and len(before) > 5:
                title = before[-60:].strip()

            resources.append({
                "title": title,
                "url": url,
                "note": f"来自 {sender}" if sender else "",
            })

    # Also check analysis frequent_links
    return resources[:8]


def extract_quotes_from_messages(messages: list[dict]) -> list[dict]:
    """Extract notable quotes from messages."""
    quotes = []
    seen = set()

    for msg in messages:
        content = msg.get("content", "") or msg.get("text", "")
        sender = msg.get("sender", msg.get("who", ""))
        if not content or not sender:
            continue

        cleaned = clean_msg(content)
        if not cleaned or len(cleaned) < 20:
            continue

        # Skip if we've seen similar text
        key = cleaned[:30]
        if key in seen:
            continue
        seen.add(key)

        # Skip bot/system messages and merged chat records
        if sender in ("管家",):
            continue
        if cleaned.startswith("[合并聊天记录]"):
            continue

        quotes.append({
            "text": cleaned[:150],
            "who": sender,
        })

    # Sort by length (prefer longer, more substantive quotes)
    quotes.sort(key=lambda q: len(q["text"]), reverse=True)
    return quotes[:6]


def auto_summary(analysis: dict[str, Any]) -> dict[str, Any]:
    """Generate a minimal summary from analysis data."""
    grp = analysis.get("group_name", "IGN AI")
    dr = analysis.get("date_range", {})
    since = dr.get("since", "")
    until = dr.get("until", "")
    time_range = f"{since} ~ {until}" if since != until else since

    kw = analysis.get("keyword_hits", [])
    kw_str = "、".join(k.get("keyword", "") for k in kw[:3]) if kw else "AI工具"

    return {
        "group_name": grp,
        "group_id": analysis.get("group_id", ""),
        "time_range": time_range,
        "headline": f"{since} 群聊精华",
        "subheadline": f"当日共 {analysis.get('total_messages', 0)} 条消息，{analysis.get('active_senders', 0)} 人参与讨论",
        "opening": f"{grp} 在 {time_range} 内产生了 {analysis.get('total_messages', 0)} 条消息。",
        "main_threads": [],
        "people": [],
        "timeline": [],
        "quotes": [],
        "links": [],
        "next_actions": [],
    }


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

.card-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}}

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
  line-height: 1.6;
}}
.topic-quote .attribution {{
  display: block;
  margin-top: 6px;
  font-size: 11px;
  color: var(--muted);
  font-style: normal;
}}
.topic-extra {{
  margin-top: 8px;
  font-size: 12px;
  color: var(--muted2);
}}

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
.need-content {{ flex: 1; }}
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
.need-meta .connector {{ color: var(--signal); }}

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
.resource-item:hover {{ border-color: rgba(249,115,22,0.3); }}
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
.resource-info {{ flex: 1; min-width: 0; }}
.resource-title {{
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.resource-note {{ font-size: 12px; color: var(--muted); }}

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
.star-card:hover {{ border-color: rgba(249,115,22,0.3); }}
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
.star-info {{ flex: 1; min-width: 0; }}
.star-name {{
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.star-count {{ font-size: 11px; color: var(--muted); }}
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
.word-tag:hover {{ transform: scale(1.05); }}

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
  content: "\\201C";
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

.footer {{
  max-width: var(--max);
  margin: 0 auto;
  padding: 32px 24px;
  text-align: center;
  color: var(--muted2);
  font-size: 12px;
}}
.footer a {{ color: var(--muted); }}

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
            attribution = t.get("attribution", "")
            attr_html = f'<span class="attribution">—— {e(attribution)}</span>' if attribution else ""
            quote_html = f'<div class="topic-quote">{e(t["insight"])}{attr_html}</div>'

        # Show extra quotes if available
        extra_html = ""
        extra_quotes = t.get("quotes", [])
        if len(extra_quotes) > 1:
            q = extra_quotes[1]
            extra_html = f'<div class="topic-extra">另有 {e(q["sender"])}: {e(q["text"][:60])}…</div>'

        cards += f"""
    <div class="topic-card">
      <div class="topic-header">
        <span class="topic-keyword">#{e(t["keyword"])}</span>
        <span class="topic-count">{t["count"]} 次提及</span>
      </div>
      <div class="topic-title">{e(t["title"])}</div>
      <div class="topic-summary">{e(t["summary"])}</div>
      {quote_html}
      {extra_html}
    </div>"""

    return f"""
<div class="section">
  <div class="section-header">
    <h2>热点话题</h2>
    <span class="badge">{len(topics)} 个</span>
  </div>
  <p class="section-desc">群内讨论最集中的关键词，附真实聊天引用</p>
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
    colors = [
        ("#f97316", "#fb923c"),
        ("#5da9ff", "#7cc8ff"),
        ("#a78bfa", "#c4b5fd"),
        ("#34d399", "#6ee7b7"),
        ("#f472b6", "#f9a8d4"),
    ]
    for i, s in enumerate(stars):
        pct = (s["count"] / max_count * 100) if max_count else 0
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

    colors = [
        ("#f97316", "rgba(249,115,22,0.12)"),
        ("#5da9ff", "rgba(93,169,255,0.12)"),
        ("#a78bfa", "rgba(167,139,250,0.12)"),
        ("#34d399", "rgba(52,211,153,0.12)"),
        ("#f472b6", "rgba(244,114,182,0.12)"),
        ("#fbbf24", "rgba(251,191,36,0.12)"),
    ]

    tags = ""
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
  <p style="margin-top:12px"><a href="https://qianzhu.online/community/ignai/DP/">← 返回日报档案</a></p>
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
        summary = read_json(Path(args.summary).expanduser().resolve())
    else:
        summary = auto_summary(analysis)

    # Load logo
    logo_data_uri = ""
    if args.logo:
        logo_path = Path(args.logo).expanduser().resolve()
        if logo_path.exists():
            ext = logo_path.suffix.lower().lstrip(".")
            mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "svg": "image/svg+xml"}.get(ext, "image/png")
            data = logo_path.read_bytes()
            logo_data_uri = f"data:{mime};base64,{base64.b64encode(data).decode()}"

    # Date string for filtering
    dr = analysis.get("date_range", {})
    date_str = dr.get("since", "")

    # Load messages
    messages = load_messages(args.messages, analysis, date_str)

    # Extract content sections from real messages
    if messages:
        topics = extract_topics_from_messages(messages, analysis)
        needs = extract_needs_from_messages(messages)
        resources = extract_resources_from_messages(messages)
        quotes = extract_quotes_from_messages(messages)
    else:
        topics = extract_topics_from_analysis(analysis, summary)
        needs = []
        resources = []
        quotes = []

    # These always come from analysis
    stars = [{"name": ts["name"], "count": ts["count"], "initial": ts["name"][0] if ts["name"] else "?"}
             for ts in analysis.get("top_senders", [])[:10]]

    words = []
    for kw in analysis.get("keyword_hits", [])[:20]:
        words.append({"word": kw["keyword"], "count": kw["count"]})
    if words:
        max_c = max(w["count"] for w in words)
        for w in words:
            w["weight"] = max(0.5, w["count"] / max_c)

    # Render
    html_content = render_full_html(summary, analysis, topics, needs, resources, stars, words, quotes, logo_data_uri)

    # Output path
    if args.output:
        out_path = Path(args.output).expanduser().resolve()
    else:
        group_dir = analysis_path.parent.parent
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
