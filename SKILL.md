---
name: wx-summary-skill
description: Interactive WeChat group digest workflow. Reuse saved recent groups, let the user choose a time preset or custom range, then generate either a structured text summary or a local web digest from real wx-cli chat data. Use when the user asks for 微信群聊日报、群聊摘要、群聊信息报、summary from WeChat chat history, or wants a reusable skill that wraps wx-cli / baoyu-style setup without deployment.
license: MIT
metadata:
  openclaw:
    homepage: https://github.com/qianzhu18/wx-summary-skill
---

# WeChat Summary Skill

把微信群聊提取做成一个可复用、可交互的摘要流程。

这个 skill 只负责:

1. 选择群聊
2. 选择时间范围
3. 选择输出模式
4. 保存最近使用的群和默认配置
5. 生成文字摘要或本地网页信息报

它不负责部署。

## User Input Rule

When asking the user for choices:

1. Prefer built-in user-input tools exposed by the runtime.
2. If no such tool exists, ask concise numbered questions in plain text.
3. Batch compatible questions when possible.

## Prerequisites

When running the bundled Python scripts below:

- use `python3` on macOS / Linux
- use `py -3` on Windows PowerShell
- use `python` only if that is your machine's Python 3 launcher

Before doing anything else, verify these in order:

```bash
python3 scripts/bootstrap_skill.py
python3 scripts/check_wechat_env.py
```

If the repo was just cloned and has no local config yet, `bootstrap_skill.py` may create it for the user before the doctor runs.

For users who want the lower-level check only:

```bash
python3 scripts/check_wechat_env.py
```

If the doctor fails:

1. tell the user the exact failing command
2. read [references/setup-without-baoyu.md](references/setup-without-baoyu.md)
3. guide them through upstream `wx-cli` install / init before continuing

This skill should reuse existing baoyu preferences when available, but it must also work without baoyu by using repo-native config.

## Shared Config

This skill reads two layers of local configuration:

1. **repo-native config** for `data_root`, optional `self_wxid`, `self_display`, and optional `wx_bin`
2. **baoyu preferences** for `self_wxid`, `self_display`, and optional `data_root`
3. **skill state** for recent groups and preferred output presets

Load the skill state first:

```bash
python3 scripts/skill_state.py inspect
```

That command returns:

- the resolved config paths
- recent groups
- default time preset
- default summary mode
- default text/web styles
- default data root

If there is no repo-native config and no baoyu config yet, initialize one:

```bash
python3 scripts/skill_state.py init-config --scope project --data-root ./wechat
```

Use the returned `recent_group_choices` as the first question. If there are no saved groups yet, the list should effectively be `Other`.

## Interaction Flow

### 1. Pick the group

Start from the saved recent groups returned by `scripts/skill_state.py inspect`.

- If the user picks a recent group, reuse its `group_id` and `group_name`.
- If the user picks `Other`, ask for the target group name or keyword, then run:

```bash
wx contacts --query "<group keyword>" --json
```

Filter to chatrooms only (`username` ending in `@chatroom`).

- If one match remains, use it.
- If multiple match, ask the user to choose.
- If none match, fall back to:

```bash
wx sessions --json
```

and search there before giving up.

The user's chosen group should be saved back into the recent-group list after the run.

### 2. Pick the time range

Offer these presets first:

- `1d` - 1 day
- `3d` - 3 days
- `7d` - 1 week
- `14d` - 2 weeks
- `30d` - 1 month
- `custom`

Use the saved default preset as the recommended option.

For preset ranges, resolve absolute dates with:

```bash
python3 scripts/resolve_time_range.py --preset 7d
```

For `custom`, ask the user for `since` and `until` in `YYYY-MM-DD`, then run:

```bash
python3 scripts/resolve_time_range.py --since YYYY-MM-DD --until YYYY-MM-DD
```

### 3. Pick the output mode

Offer:

- `text` - structured text digest
- `webpage` - local web digest

Use the saved default summary mode as the recommended option.

### 4. Pick the style

Use the saved style default for the chosen mode.

Current built-in styles:

- text mode: `growth-brief-v1`
- webpage mode: `daily-report-v1`

Do not ask an extra style question unless:

- the user explicitly asks to change style, or
- more than one style is available for that mode

### 5. Save the session defaults

After the user confirms group + time range + mode, persist them:

```bash
python3 scripts/skill_state.py save-session \
  --scope project \
  --group-id "<group_id>" \
  --group-name "<group_name>" \
  --duration-preset 7d \
  --summary-mode text \
  --text-style growth-brief-v1 \
  --web-style daily-report-v1
```

Rules:

- Keep only the most recent groups near the front of the list.
- Default to `project` scope unless the user explicitly asks for global reuse.
- If the user asks for global reuse across projects, use `xdg` scope.

## Fetch + Analyze

Once group and date range are fixed, always build a local analysis bundle first:

```bash
python3 scripts/prepare_wechat_digest.py \
  --chat "<group_name>" \
  --since YYYY-MM-DD \
  --until YYYY-MM-DD \
  --data-root "<data_root>"
```

This writes:

- `raw/*.messages.json`
- `raw/*.stats.json`
- `analysis/*.analysis.json`
- `analysis/*.briefing.md`

Read the generated briefing before opening raw messages. It is the cheapest way to understand the selected range.

## Output Modes

### Text mode

Read:

- `references/text-summary-format.md`

Use the analysis bundle plus raw messages only when needed, then write a markdown digest to:

```text
<group_dir>/<since>_<until>.text-summary.md
```

The final text output must follow the section structure in `references/text-summary-format.md`.

### Webpage mode

Read:

- `references/webpage-mode.md`
- `references/summary-schema.md`

Then:

1. Draft `summary.json`
2. Render the local site with:

```bash
python3 scripts/render_web_digest.py \
  --summary /abs/path/to/summary.json \
  --analysis /abs/path/to/analysis.json
```

This writes local output only:

- `<group_dir>/<since>_<until>.web.md`
- `<group_dir>/site/index.html`
- `<group_dir>/dist/index.html`
- `<group_dir>/history.json`

Do not add deployment steps.

## When To Read Raw Messages

The analysis bundle is usually enough. Open raw messages only when:

- a quote needs verification
- a hotspot feels too vague
- you need the exact wording for demand / connector attribution
- the same nickname might refer to multiple people

Do not dump the whole raw payload into context if the date range is large. Use `jq` slices or targeted searches.

## Output Discipline

- Use real group names and real participant names.
- Keep counts and dates accurate.
- Keep explicit facts separate from your inference.
- Do not fabricate links.
- Do not add deployment advice unless the user explicitly asks for it.
