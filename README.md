# wx-summary-skill

An interactive WeChat group summary skill for Codex / Claude-style agent workflows.

It wraps `wx-cli` chat extraction into a reusable flow:

1. pick a saved recent group or choose `Other`
2. choose a time preset or custom date range
3. choose output mode: text summary or local web digest
4. persist recent groups and defaults for reuse
5. generate structured local artifacts from real WeChat chat history

This repository focuses on extraction, analysis, and local rendering. It intentionally does **not** include deployment.

## Why this exists

Most WeChat summary prompts are one-off and forget everything about the last run.

`wx-summary-skill` turns that into a reusable experience:

- remembers recent groups
- remembers preferred time preset and output mode
- reuses existing baoyu / `wx-cli` identity config when available
- supports both a structured markdown digest and a local HTML digest
- keeps the workflow local and inspectable

## Features

- interactive group selection
- recent-group memory with `Other` fallback
- built-in time presets: `1d`, `3d`, `7d`, `14d`, `30d`, `custom`
- two output modes:
  - `text`: structured summary for reading and follow-up
  - `webpage`: static local digest page
- reusable local state
- real-message analysis bundle with stats, quotes, link titles, and activity patterns

## Repository layout

```text
.
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── summary-schema.md
│   ├── text-summary-format.md
│   └── webpage-mode.md
└── scripts/
    ├── prepare_wechat_digest.py
    ├── render_web_digest.py
    ├── resolve_time_range.py
    └── skill_state.py
```

## Prerequisites

You need:

- Python 3
- [`wx-cli`](https://github.com/jackwener/wx-cli) available as `wx`
- WeChat running and readable by `wx-cli`

Quick checks:

```bash
wx --version
wx sessions --json
```

If those do not work, fix your `wx-cli` / WeChat environment first.

## Installation

Install this repository into your preferred local skills directory, or symlink it there.

Typical flow:

```bash
git clone https://github.com/qianzhu18/wx-summary-skill.git
```

Then place or link the folder into the skill directory used by your agent runtime.

Once installed, invoke it with:

```text
$wx-summary-skill
```

## Shared configuration

This skill reads two layers of local config:

1. baoyu-style WeChat preferences, when available
2. its own local state for recent groups and defaults

### Reused baoyu config

If one of these exists, the skill will reuse it:

- `.baoyu-skills/baoyu-wechat-summary/EXTEND.md` relative to the project root
- `${XDG_CONFIG_HOME:-$HOME/.config}/baoyu-skills/baoyu-wechat-summary/EXTEND.md`
- `$HOME/.baoyu-skills/baoyu-wechat-summary/EXTEND.md`

Useful keys:

- `self_wxid`
- `self_display`
- `data_root`

### Skill state

State is stored in one of:

- project scope: `<project>/.wx-summary-skill/state.json`
- XDG scope: `${XDG_CONFIG_HOME:-$HOME/.config}/wx-summary-skill/state.json`
- home scope: `$HOME/.wx-summary-skill/state.json`

The default write scope is `project`.

Inspect current merged state:

```bash
python3 scripts/skill_state.py inspect
```

Save a session:

```bash
python3 scripts/skill_state.py save-session \
  --scope project \
  --group-id "44137533350@chatroom" \
  --group-name "Christina的AI+ 知识圈" \
  --duration-preset 7d \
  --summary-mode text \
  --text-style growth-brief-v1 \
  --web-style daily-report-v1
```

## Time range resolution

Preset ranges resolve to absolute dates with:

```bash
python3 scripts/resolve_time_range.py --preset 7d
```

Custom dates:

```bash
python3 scripts/resolve_time_range.py --since 2026-05-11 --until 2026-05-17
```

## Output modes

### 1. Text summary

The text mode is designed for actionable reading and personal growth review.

Expected section structure:

- `群聊总结`
- `热点`
- `需求与链接人`
- `资源`
- `活跃之星`
- `词云`

See:

- [references/text-summary-format.md](references/text-summary-format.md)

### 2. Webpage mode

The webpage mode creates a local static digest site.

It uses:

- a reviewed `summary.json`
- an `analysis.json`
- the renderer in `scripts/render_web_digest.py`

See:

- [references/summary-schema.md](references/summary-schema.md)
- [references/webpage-mode.md](references/webpage-mode.md)

## Typical workflow

### 1. Inspect state

```bash
python3 scripts/skill_state.py inspect
```

### 2. Resolve the range

```bash
python3 scripts/resolve_time_range.py --preset 7d
```

### 3. Build the analysis bundle

```bash
python3 scripts/prepare_wechat_digest.py \
  --chat "Christina的AI+ 知识圈" \
  --since 2026-05-11 \
  --until 2026-05-17 \
  --data-root "./wechat"
```

### 4A. Produce a text summary

Read the generated briefing and raw evidence as needed, then write:

```text
<group_dir>/2026-05-11_2026-05-17.text-summary.md
```

### 4B. Produce a local web digest

```bash
python3 scripts/render_web_digest.py \
  --summary /abs/path/to/summary.json \
  --analysis /abs/path/to/analysis.json
```

This writes local artifacts such as:

- `<group_dir>/site/index.html`
- `<group_dir>/dist/index.html`
- `<group_dir>/history.json`

## What gets generated

`prepare_wechat_digest.py` creates:

- `raw/*.messages.json`
- `raw/*.stats.json`
- `analysis/*.analysis.json`
- `analysis/*.briefing.md`

`render_web_digest.py` additionally creates:

- `<group_dir>/<since>_<until>.web.md`
- `<group_dir>/summary.json`
- `<group_dir>/site/index.html`
- `<group_dir>/dist/index.html`
- `<group_dir>/history.json`
- `<group_dir>/history-digests.jsonl`

## Design notes

- The skill prefers structured local state over one-off prompting.
- The analysis bundle is the default reading surface; raw messages are only opened when necessary.
- Deployment is intentionally excluded so the repository stays focused on reusable summarization.

## Development

Quick local checks:

```bash
python3 -m py_compile scripts/*.py
```

If you have the Codex `skill-creator` validator available locally, also run:

```bash
python3 path/to/quick_validate.py .
```

If you do not have that validator locally, the core minimum is:

```bash
python3 -m py_compile scripts/*.py
```

## License

MIT. See [LICENSE](LICENSE).
