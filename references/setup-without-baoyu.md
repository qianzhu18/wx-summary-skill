# Setup Without baoyu

Read this only when one of these is true:

- `wx` is not installed
- `wx sessions --json` fails
- you want to use `wx-summary-skill` without `baoyu-wechat-summary`

## 1. Install wx-cli

Official upstream:

- GitHub: <https://github.com/jackwener/wx-cli>

Choose one install path:

```bash
npm install -g @jackwener/wx-cli
```

or:

```bash
curl -fsSL https://raw.githubusercontent.com/jackwener/wx-cli/main/install.sh | bash
```

If you also want the upstream `wx-cli` skill itself:

```bash
npx skills add jackwener/wx-cli -g
```

## 2. macOS initialization

On macOS, follow the upstream initialization flow before using this repo:

```bash
sudo codesign --force --deep --sign - /Applications/WeChat.app
open -a WeChat
sudo wx init
wx sessions --json
```

If your WeChat app is not under `/Applications/WeChat.app`, replace the path.

`wx sessions --json` should return JSON before you continue.

## 3. Save repo-native config

If you are not reusing baoyu defaults, initialize the local config once:

```bash
python3 scripts/skill_state.py init-config --scope project --data-root ./wechat
```

Use `--scope xdg` if you want one shared config across multiple projects.

## 4. Run the doctor

Before invoking the skill, verify the whole stack:

```bash
python3 scripts/check_wechat_env.py
```

When the doctor returns `ready`, you can call:

```text
$wx-summary-skill
```
