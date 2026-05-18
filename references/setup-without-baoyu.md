# Setup Without baoyu

Read this only when one of these is true:

- `wx` is not installed
- `wx sessions --json` fails
- you want to use `wx-summary-skill` without `baoyu-wechat-summary`

If you just cloned the repo from GitHub, the easiest entry is:

- macOS / Linux: `python3 scripts/bootstrap_skill.py`
- Windows PowerShell: `py -3 scripts/bootstrap_skill.py`

That command auto-creates repo-native config when needed and then runs the doctor.

## 1. Install wx-cli

Official upstream:

- GitHub: <https://github.com/jackwener/wx-cli>

Use `python3` on macOS / Linux and `py -3` on Windows PowerShell for this repo's helper scripts.

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

If you also want the upstream `wx-cli` skill itself:

```bash
npx skills add jackwener/wx-cli -g
```

## 2. Initialize by platform

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

If your macOS WeChat app is not under `/Applications/WeChat.app`, replace the path.

`wx sessions --json` should return JSON before you continue.

On Windows and Linux, keep desktop WeChat running and fully logged in before `wx init`.

## 3. Optional: save repo-native config manually

If you want to override what bootstrap would write, or if you prefer a shared config scope, initialize the local config manually:

```bash
python3 scripts/skill_state.py init-config --scope project --data-root ./wechat
```

Windows PowerShell:

```powershell
py -3 scripts/skill_state.py init-config --scope project --data-root .\wechat
```

Use `--scope xdg` if you want one shared config across multiple projects.

## 4. Run the bootstrap path

macOS / Linux:

```bash
python3 scripts/bootstrap_skill.py
```

Windows PowerShell:

```powershell
py -3 scripts/bootstrap_skill.py
```

## 5. Run the doctor

Before invoking the skill, verify the whole stack:

```bash
python3 scripts/check_wechat_env.py
```

Windows PowerShell:

```powershell
py -3 scripts/check_wechat_env.py
```

## 6. Start the skill

When the doctor returns `ready`, you can call:

```text
$wx-summary-skill
```
