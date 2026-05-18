# wx-summary-skill

An interactive WeChat group digest skill for Codex / Claude-style agent workflows.

It turns one-off WeChat summary prompts into a reusable local flow:

1. pick a saved recent group or choose `Other`
2. choose a time preset or custom date range
3. choose output mode: text summary or local web digest
4. persist recent groups and defaults for reuse
5. generate structured local artifacts from real WeChat chat history

This repository focuses on extraction, analysis, and local rendering. It intentionally does **not** include deployment.

## Real usage example

This screenshot is a real run from the skill, hosted through the same O-Publish + Cloudflare R2 image workflow used in the author's publishing setup.

![wx-summary-skill real usage example](https://img.qianzhu.online/skills/wx-summary-skill/readme/wx-summary-skill-ign-ai-yanglai-example-2026-05-18.png)

Case:

- group: `IGN AI | 洋来`
- range: `7d`
- mode: `text`

Example reply:

```text
IGN AI | 洋来，7d，text
```

The source file used for this README example is kept in [docs/assets/wx-summary-skill-ign-ai-yanglai-example-2026-05-18.png](docs/assets/wx-summary-skill-ign-ai-yanglai-example-2026-05-18.png).

## Why this exists

Most WeChat summary prompts forget everything about the previous run.

`wx-summary-skill` keeps a small amount of reusable state:

- remembers recent groups
- remembers preferred time preset and output mode
- reuses existing baoyu defaults when available
- still works without baoyu through repo-native config
- supports both a structured markdown digest and a local HTML digest
- keeps the workflow local and inspectable

## What this repo does

- interactive group selection
- recent-group memory with `Other` fallback
- built-in time presets: `1d`, `3d`, `7d`, `14d`, `30d`, `custom`
- two output modes:
  - `text`: structured summary for reading and follow-up
  - `webpage`: static local digest page
- reusable local state
- real-message analysis bundle with stats, quotes, link titles, and activity patterns

## What this repo does not do

- it does not fetch WeChat data by itself without `wx-cli`
- it does not require `baoyu-wechat-summary`, but it can reuse baoyu config when present
- it does not deploy HTML output

## Install the skill

Clone directly into your Codex skills directory:

```bash
git clone https://github.com/qianzhu18/wx-summary-skill.git "$HOME/.codex/skills/wx-summary-skill"
```

After bootstrap returns `ready`, invoke it with:

```text
$wx-summary-skill
```

If you prefer another local skill directory, clone or symlink this repo there instead.

## Quickstart

If you want the shortest path from a GitHub clone to a usable local setup, run the bootstrap script right after cloning.

macOS / Linux:

```bash
git clone https://github.com/qianzhu18/wx-summary-skill.git "$HOME/.codex/skills/wx-summary-skill"
cd "$HOME/.codex/skills/wx-summary-skill"
python3 scripts/bootstrap_skill.py
```

Windows PowerShell:

```powershell
git clone https://github.com/qianzhu18/wx-summary-skill.git "$HOME\.codex\skills\wx-summary-skill"
Set-Location "$HOME\.codex\skills\wx-summary-skill"
py -3 scripts/bootstrap_skill.py
```

The bootstrap script:

- creates repo-native config automatically when it is missing
- detects whether baoyu config is already reusable
- runs the built-in doctor
- prints the exact next commands for your platform
- exits `ready` only when the machine can already read WeChat sessions
- leaves you with a repo that can be used directly from the GitHub clone path

## Platform support

According to the official `wx-cli` README, the upstream install/init flow covers:

- macOS Apple Silicon / Intel
- Linux x86_64 / arm64
- Windows x86_64

This repo follows that same platform model. The only important command difference is:

- macOS / Linux: use `python3`
- Windows PowerShell: use `py -3`
- if your machine exposes only `python` for Python 3, use that instead

The built-in doctor and bootstrap path are both platform-aware and print platform-specific next steps.

## Start from zero: no baoyu, no wx-cli

This is the missing path that confused earlier versions of the repo.

`wx-summary-skill` only needs [`wx-cli`](https://github.com/jackwener/wx-cli) plus a readable WeChat session. `baoyu-wechat-summary` is optional.

### 1. Install `wx-cli`

Official upstream repo:

- [jackwener/wx-cli](https://github.com/jackwener/wx-cli)

Choose one install path:

```bash
npm install -g @jackwener/wx-cli
```

macOS / Linux shell installer:

```bash
curl -fsSL https://raw.githubusercontent.com/jackwener/wx-cli/main/install.sh | bash
```

Windows PowerShell installer:

```powershell
irm https://raw.githubusercontent.com/jackwener/wx-cli/main/install.ps1 | iex
```

If you also want the upstream `wx-cli` skill itself for your agent runtime:

```bash
npx skills add jackwener/wx-cli -g
```

### 2. Initialize `wx-cli` by platform

macOS:

```bash
sudo codesign --force --deep --sign - /Applications/WeChat.app
open -a WeChat
sudo wx init
wx sessions --json
```

Windows PowerShell, run as Administrator:

```powershell
wx init
wx sessions --json
```

Linux:

```bash
sudo wx init
wx sessions --json
```

Notes:

- if your WeChat app is not under `/Applications/WeChat.app`, replace the path
- on Windows and Linux, keep desktop WeChat running and fully logged in before `wx init`
- `wx sessions --json` should return real JSON before you continue
- if it fails, rerun the exact failing command first before blaming the summary layer

### 3. Run the bootstrap path

The fastest path for direct GitHub users is:

macOS / Linux:

```bash
cd "$HOME/.codex/skills/wx-summary-skill"
python3 scripts/bootstrap_skill.py
```

Windows PowerShell:

```powershell
Set-Location "$HOME\.codex\skills\wx-summary-skill"
py -3 scripts/bootstrap_skill.py
```

This bootstrap command will initialize repo-native config when needed, then run the doctor for you.

### 4. Run the built-in doctor

This repo now includes an environment check script:

macOS / Linux:

```bash
cd "$HOME/.codex/skills/wx-summary-skill"
python3 scripts/check_wechat_env.py
```

Windows PowerShell:

```powershell
Set-Location "$HOME\.codex\skills\wx-summary-skill"
py -3 scripts/check_wechat_env.py
```

The doctor checks:

- whether `wx` is in `PATH`
- whether `wx --version` works
- whether `wx sessions --json` is readable
- whether this repo already has a local config
- where the default data root will be written

If the doctor reports `action-needed`, it prints the next commands to run.

### 5. Optional: save repo-native config manually

If you want to override what bootstrap would write, or if you prefer a shared config scope, initialize local config manually:

```bash
python3 scripts/skill_state.py init-config --scope project --data-root ./wechat
```

Windows PowerShell:

```powershell
py -3 scripts/skill_state.py init-config --scope project --data-root .\wechat
```

If you want one config shared across multiple projects:

```bash
python3 scripts/skill_state.py init-config --scope xdg --data-root ~/wechat-data
```

### 6. Start the skill

Once the doctor returns `ready`, run:

```text
$wx-summary-skill
```

## Already have baoyu / wx-cli

If you already use `baoyu-wechat-summary` or a working `wx-cli` setup, the repo will reuse that config automatically when one of these exists:

- `.baoyu-skills/baoyu-wechat-summary/EXTEND.md` relative to the project root
- `${XDG_CONFIG_HOME:-$HOME/.config}/baoyu-skills/baoyu-wechat-summary/EXTEND.md`
- `$HOME/.baoyu-skills/baoyu-wechat-summary/EXTEND.md`

Useful reused keys:

- `self_wxid`
- `self_display`
- `data_root`

## Repo-native config and state

This repo now has its own config layer, so it no longer depends on baoyu to be useful.

### Config

Config is read from the first existing file in this order:

- `<project>/.wx-summary-skill/config.json`
- `${XDG_CONFIG_HOME:-$HOME/.config}/wx-summary-skill/config.json`
- `$HOME/.wx-summary-skill/config.json`

Supported keys:

- `data_root`
- `self_wxid` (optional)
- `self_display` (optional)
- `wx_bin` (optional, default: `wx`)

### State

State is read from the first existing file in this order:

- `<project>/.wx-summary-skill/state.json`
- `${XDG_CONFIG_HOME:-$HOME/.config}/wx-summary-skill/state.json`
- `$HOME/.wx-summary-skill/state.json`

State stores:

- recent groups
- default time preset
- default summary mode
- default text style
- default webpage style

Inspect the merged view any time:

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

## Typical workflow

Below, the examples use the macOS / Linux launcher form. On Windows, replace `python3` with `py -3`.

### 1. Check the environment

```bash
python3 scripts/bootstrap_skill.py
```

Or run the lower-level doctor directly:

```bash
python3 scripts/check_wechat_env.py
```

### 2. Inspect state

```bash
python3 scripts/skill_state.py inspect
```

### 3. Resolve the range

```bash
python3 scripts/resolve_time_range.py --preset 7d
```

Custom dates:

```bash
python3 scripts/resolve_time_range.py --since 2026-05-11 --until 2026-05-17
```

### 4. Build the analysis bundle

```bash
python3 scripts/prepare_wechat_digest.py \
  --chat "Christina的AI+ 知识圈" \
  --since 2026-05-11 \
  --until 2026-05-17 \
  --data-root "./wechat"
```

### 5A. Produce a text summary

Read the generated briefing and raw evidence as needed, then write:

```text
<group_dir>/2026-05-11_2026-05-17.text-summary.md
```

Expected section structure:

- `群聊总结`
- `热点`
- `需求与链接人`
- `资源`
- `活跃之星`
- `词云`

See [references/text-summary-format.md](references/text-summary-format.md).

### 5B. Produce a local web digest

```bash
python3 scripts/render_web_digest.py \
  --summary /abs/path/to/summary.json \
  --analysis /abs/path/to/analysis.json
```

See:

- [references/summary-schema.md](references/summary-schema.md)
- [references/webpage-mode.md](references/webpage-mode.md)

## What gets generated

`prepare_wechat_digest.py` creates:

- `raw/*.messages.json`
- `raw/*.stats.json`
- `analysis/*.analysis.json`
- `analysis/*.briefing.md`

`render_web_digest.py` writes local artifacts such as:

- `<group_dir>/<since>_<until>.web.md`
- `<group_dir>/site/index.html`
- `<group_dir>/dist/index.html`
- `<group_dir>/history.json`

## Repository layout

```text
.
├── SKILL.md
├── LICENSE
├── README.md
├── agents/
│   └── openai.yaml
├── docs/
│   └── assets/
│       ├── wx-summary-skill-ign-ai-yanglai-example-2026-05-18.png
│       └── wx-summary-skill-usage-example-2026-05-18.png
├── .github/
│   └── workflows/
│       └── selftest.yml
├── references/
│   ├── setup-without-baoyu.md
│   ├── summary-schema.md
│   ├── text-summary-format.md
│   └── webpage-mode.md
└── scripts/
    ├── bootstrap_skill.py
    ├── check_wechat_env.py
    ├── prepare_wechat_digest.py
    ├── render_web_digest.py
    ├── resolve_time_range.py
    ├── selftest_repo.py
    └── skill_state.py
```

## Selftest

Run the repository smoke test locally with:

```bash
python3 scripts/selftest_repo.py
```

It validates the bootstrap path plus the platform-specific doctor branches. The same smoke test runs in GitHub Actions on macOS, Linux, and Windows.

## License

MIT. See [LICENSE](LICENSE).
