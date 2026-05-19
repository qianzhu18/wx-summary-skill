#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from skill_state import inspect_payload, project_root_from


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check whether wx-summary-skill can read WeChat data on this machine."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of human text.")
    parser.add_argument(
        "--platform",
        help="Override detected platform for smoke tests or docs validation (darwin/linux/win32).",
    )
    return parser.parse_args()


def run_command(cmd: list[str]) -> dict[str, Any]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "command": " ".join(cmd),
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def step(title: str, command: str, why: str) -> dict[str, str]:
    return {"title": title, "command": command, "why": why}


def normalized_platform(raw_platform: str | None) -> str:
    platform_id = raw_platform or sys.platform
    if platform_id.startswith("linux"):
        return "linux"
    if platform_id.startswith("win") or platform_id in {"cygwin", "msys"}:
        return "win32"
    if platform_id == "darwin":
        return "darwin"
    return platform_id


def platform_label(platform_id: str) -> str:
    return {
        "darwin": "macOS",
        "linux": "Linux",
        "win32": "Windows",
    }.get(platform_id, platform_id)


def python_command(platform_id: str) -> str:
    if platform_id == "win32":
        return "py -3"
    return "python3"


def config_init_command(platform_id: str) -> str:
    data_root = ".\\wechat" if platform_id == "win32" else "./wechat"
    return (
        f"{python_command(platform_id)} scripts/skill_state.py init-config "
        f"--scope project --data-root {data_root}"
    )


def manual_fallback_command(platform_id: str) -> str:
    py = python_command(platform_id)
    return (
        f'{py} scripts/prepare_wechat_digest.py --chat "<群名>" '
        f"--since YYYY-MM-DD --until YYYY-MM-DD --source clipboard"
    )


def load_json_object(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict):
        return payload
    return None


def resolve_relative_path(base_dir: Path, raw_path: str | None, default_name: str) -> Path:
    candidate = raw_path or default_name
    path = Path(candidate).expanduser()
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def count_db_files(root: Path) -> int:
    if not root.exists() or not root.is_dir():
        return 0
    return sum(1 for path in root.rglob("*.db") if path.is_file())


def latest_db_mtime(root: Path) -> float:
    newest = 0.0
    if not root.exists() or not root.is_dir():
        return newest
    for path in root.rglob("*.db"):
        if not path.is_file():
            continue
        try:
            newest = max(newest, path.stat().st_mtime)
        except OSError:
            continue
    return newest


def windows_ini_roots() -> list[dict[str, Any]]:
    appdata = os.getenv("APPDATA")
    if not appdata:
        return []
    config_dir = Path(appdata).expanduser() / "Tencent" / "xwechat" / "config"
    if not config_dir.is_dir():
        return []

    roots: list[dict[str, Any]] = []
    for ini_path in sorted(config_dir.glob("*.ini")):
        try:
            data_root = ini_path.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            data_root = ""
        root_path = Path(data_root).expanduser() if data_root else None
        roots.append(
            {
                "ini_path": str(ini_path),
                "data_root": data_root or None,
                "exists": bool(root_path and root_path.is_dir()),
            }
        )
    return roots


def windows_detected_db_dirs() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in windows_ini_roots():
        data_root = item.get("data_root")
        if not data_root:
            continue
        xwechat_root = Path(data_root).expanduser() / "xwechat_files"
        if not xwechat_root.is_dir():
            continue
        for wxid_dir in sorted(xwechat_root.iterdir()):
            db_dir = wxid_dir / "db_storage"
            if not db_dir.is_dir():
                continue
            db_dir_str = str(db_dir.resolve())
            if db_dir_str in seen:
                continue
            seen.add(db_dir_str)
            candidates.append(
                {
                    "db_dir": db_dir_str,
                    "db_file_count": count_db_files(db_dir),
                    "latest_db_mtime": latest_db_mtime(db_dir),
                }
            )
    candidates.sort(key=lambda item: item["latest_db_mtime"], reverse=True)
    return candidates


def inspect_wx_cli_state(platform_id: str) -> dict[str, Any]:
    cli_dir = Path.home().expanduser() / ".wx-cli"
    config_path = cli_dir / "config.json"
    config_exists = config_path.exists()
    config_payload = load_json_object(config_path) if config_exists else None

    raw_db_dir = None
    if isinstance(config_payload, dict):
        raw_db_dir = config_payload.get("db_dir")
    configured_db_dir = Path(str(raw_db_dir)).expanduser() if raw_db_dir else None
    configured_db_dir_exists = bool(configured_db_dir and configured_db_dir.is_dir())
    configured_db_file_count = count_db_files(configured_db_dir) if configured_db_dir else 0

    raw_keys_file = None
    if isinstance(config_payload, dict):
        raw_keys_file = config_payload.get("keys_file")
    keys_path = resolve_relative_path(config_path.parent, str(raw_keys_file) if raw_keys_file else None, "all_keys.json")
    keys_exists = keys_path.exists()
    keys_entries: int | None = None
    keys_parse_error: str | None = None
    if keys_exists:
        keys_payload = load_json_object(keys_path)
        if keys_payload is None:
            keys_parse_error = "keys file exists but is not valid JSON object"
        else:
            keys_entries = len(keys_payload)

    windows_roots = windows_ini_roots() if platform_id == "win32" else []
    windows_candidates = windows_detected_db_dirs() if platform_id == "win32" else []
    configured_db_dir_resolved = str(configured_db_dir.resolve()) if configured_db_dir_exists else None
    candidate_paths = {item["db_dir"] for item in windows_candidates}
    configured_db_dir_in_candidates = bool(
        configured_db_dir_resolved and configured_db_dir_resolved in candidate_paths
    )

    diagnostics: list[dict[str, str]] = []
    if configured_db_dir_exists and not keys_exists:
        diagnostics.append(
            {
                "code": "wx_cli_keys_missing",
                "summary": "wx-cli 已经指向一个存在的 db_dir，但 all_keys.json 还不存在。",
                "detail": "这说明数据目录可能没问题，最后卡点更像是密钥扫描或密钥文件落盘阶段。",
            }
        )

    if platform_id == "win32" and configured_db_dir_exists and not keys_exists:
        diagnostics.append(
            {
                "code": "windows_wx_init_reautodetects_before_keys",
                "summary": "Windows 上的 wx init 在生成 all_keys.json 之前会重新走自动探测，不会优先复用手动写入的 config.json db_dir。",
                "detail": "如果微信数据迁移到了非标准位置，或者只能靠 junction 才能找到真实目录，手改 db_dir 仍可能被 init 绕开。",
            }
        )
        if windows_candidates and not configured_db_dir_in_candidates:
            diagnostics.append(
                {
                    "code": "windows_configured_db_dir_outside_autodetect",
                    "summary": "当前 config.json 里的 db_dir 不在 wx-cli 这次 Windows 自动探测看到的候选列表里。",
                    "detail": "这通常意味着 %APPDATA%\\\\Tencent\\\\xwechat\\\\config\\\\*.ini 指向的 data_root 与真实 db_storage 所在位置不一致。",
                }
            )
        if not windows_candidates:
            diagnostics.append(
                {
                    "code": "windows_autodetect_found_no_candidates",
                    "summary": "Windows 自动探测没有找到任何 xwechat_files/<wxid>/db_storage 候选目录。",
                    "detail": "即使 daemon 能读到旧路径，只要 init 这一轮探测不到候选目录，就不会进入 all_keys.json 生成阶段。",
                }
            )

    return {
        "cli_dir": str(cli_dir),
        "config_path": str(config_path),
        "config_exists": config_exists,
        "configured_db_dir": str(configured_db_dir) if configured_db_dir else None,
        "configured_db_dir_exists": configured_db_dir_exists,
        "configured_db_file_count": configured_db_file_count,
        "keys_path": str(keys_path),
        "keys_exists": keys_exists,
        "keys_entries": keys_entries,
        "keys_parse_error": keys_parse_error,
        "windows_ini_roots": windows_roots,
        "windows_detected_db_dirs": windows_candidates,
        "configured_db_dir_in_detected_candidates": configured_db_dir_in_candidates,
        "diagnostics": diagnostics,
    }


def install_steps_for_missing_wx(platform_id: str) -> list[dict[str, str]]:
    steps = [
        step(
            "Install wx-cli with npm",
            "npm install -g @jackwener/wx-cli",
            "Official all-platform install path when you already have Node.js / npm.",
        )
    ]
    if platform_id in {"darwin", "linux"}:
        steps.append(
            step(
                "Install wx-cli with the official shell script",
                "curl -fsSL https://raw.githubusercontent.com/jackwener/wx-cli/main/install.sh | bash",
                "Official one-line installer for macOS / Linux.",
            )
        )
    elif platform_id == "win32":
        steps.append(
            step(
                "Install wx-cli with the official PowerShell script",
                "irm https://raw.githubusercontent.com/jackwener/wx-cli/main/install.ps1 | iex",
                "Official Windows install path. Run it in an Administrator PowerShell window.",
            )
        )
    steps.append(
        step(
            "Optional: add the upstream wx-cli skill",
            "npx skills add jackwener/wx-cli -g",
            "Useful if you also want a standalone skill around wx-cli itself.",
        )
    )
    return steps


def windows_followup_steps(wx_cli_state: dict[str, Any]) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []
    if wx_cli_state.get("config_exists"):
        steps.append(
            step(
                "Inspect wx-cli config",
                f'Get-Content "{wx_cli_state["config_path"]}"',
                "Confirm whether db_dir already points at a real db_storage path and whether keys_file still points to all_keys.json.",
            )
        )
    if wx_cli_state.get("windows_ini_roots"):
        steps.append(
            step(
                "Inspect WeChat data-root hints",
                'Get-ChildItem "$env:APPDATA\\Tencent\\xwechat\\config" -Filter *.ini | Get-Content',
                "wx-cli on Windows auto-detects db_storage from these .ini files before it writes all_keys.json.",
            )
        )
    if wx_cli_state.get("diagnostics"):
        steps.append(
            step(
                "Reconcile manual db_dir with auto-detect",
                "Compare ~/.wx-cli/config.json db_dir with the real data_root that owns xwechat_files\\<wxid>\\db_storage.",
                "Upstream wx-cli v0.3.0 only trusts manual db_dir after all_keys.json already exists, so a migrated/junction path can still block wx init.",
            )
        )
    return steps


def recovery_steps_for_unreadable_sessions(
    platform_id: str, wx_bin: str, wx_cli_state: dict[str, Any]
) -> list[dict[str, str]]:
    wx_init_command = f"sudo {wx_bin} init" if platform_id in {"darwin", "linux"} else f"{wx_bin} init"
    verify_command = f"{wx_bin} sessions --json"
    if platform_id == "darwin":
        return [
            step(
                "Re-sign WeChat",
                "sudo codesign --force --deep --sign - /Applications/WeChat.app",
                "wx-cli needs the desktop WeChat app to be re-signed before initialization on macOS.",
            ),
            step(
                "Restart WeChat",
                "open -a WeChat",
                "After codesign, reopen WeChat and make sure your account is logged in.",
            ),
            step(
                "Initialize wx-cli",
                wx_init_command,
                "This prepares the accessibility / memory-scan layer used by wx-cli on macOS.",
            ),
            step(
                "Verify readable sessions",
                verify_command,
                "You should see JSON output before running wx-summary-skill.",
            ),
        ]
    if platform_id == "linux":
        return [
            step(
                "Keep desktop WeChat running",
                "Launch desktop WeChat and make sure the target account is fully logged in.",
                "wx-cli reads your local desktop session data and needs the app running.",
            ),
            step(
                "Initialize wx-cli",
                wx_init_command,
                "Official upstream Linux init step.",
            ),
            step(
                "Verify readable sessions",
                verify_command,
                "You should see JSON output before running wx-summary-skill.",
            ),
        ]
    if platform_id == "win32":
        steps = [
            step(
                "Open Administrator PowerShell",
                "Start-Process PowerShell -Verb RunAs",
                "The official Windows init flow expects an elevated PowerShell session.",
            ),
            step(
                "Keep desktop WeChat running",
                "Launch desktop WeChat and make sure the target account is fully logged in.",
                "wx-cli reads your local desktop session data and needs the app running.",
            ),
            step(
                "Initialize wx-cli",
                wx_init_command,
                "Official upstream Windows init step.",
            ),
            step(
                "Verify readable sessions",
                verify_command,
                "You should see JSON output before running wx-summary-skill.",
            ),
        ]
        steps.extend(windows_followup_steps(wx_cli_state))
        return steps
    return [
        step(
            "Initialize wx-cli",
            f"{wx_bin} init",
            "If sessions are unreadable, the upstream init flow usually fixes it.",
        ),
        step(
            "Verify readable sessions",
            verify_command,
            "You should see JSON output before running wx-summary-skill.",
        ),
    ]


def manual_fallback_step(platform_id: str) -> dict[str, str]:
    shortcut = "Ctrl+A / Ctrl+C" if platform_id == "win32" else "Cmd+A / Cmd+C"
    return step(
        "Fallback: import a copied transcript instead of wx-cli",
        manual_fallback_command(platform_id),
        "If WeChat 4.x keeps blocking wx-cli, open the target chat in desktop WeChat, scroll to the first date you need, "
        f"use {shortcut}, then let prepare_wechat_digest.py parse the clipboard transcript into the same analysis bundle.",
    )


def build_report(project_root: Path, platform_override: str | None = None) -> dict[str, Any]:
    state = inspect_payload(project_root)
    resolved = state["state"]
    default_data_root = Path(resolved["default_data_root"]).expanduser()
    wx_bin = state.get("resolved_defaults", {}).get("wx_bin") or "wx"
    wx_path = shutil.which(wx_bin)
    platform_id = normalized_platform(platform_override)
    python_cmd = python_command(platform_id)

    report: dict[str, Any] = {
        "project_root": str(project_root),
        "ready": False,
        "platform": platform_id,
        "platform_label": platform_label(platform_id),
        "python_command": python_cmd,
        "wx_bin": wx_bin,
        "wx_path": wx_path,
        "checks": [],
        "diagnostics": [],
        "next_steps": [],
        "state": {
            "config_path": state.get("config_path"),
            "baoyu_extend_path": state.get("baoyu_extend_path"),
            "default_data_root": str(default_data_root),
            "default_data_root_exists": default_data_root.exists(),
        },
    }

    report["checks"].append(
        {
            "name": "wx binary",
            "ok": bool(wx_path),
            "detail": wx_path or f"{wx_bin} not found in PATH",
        }
    )

    version_check: dict[str, Any] | None = None
    sessions_check: dict[str, Any] | None = None
    sessions_count = 0
    wx_cli_state = inspect_wx_cli_state(platform_id)
    report["wx_cli"] = wx_cli_state

    if wx_path:
        report["checks"].append(
            {
                "name": "wx-cli config.json",
                "ok": wx_cli_state["config_exists"],
                "detail": wx_cli_state["config_path"]
                if wx_cli_state["config_exists"]
                else f'missing ({wx_cli_state["config_path"]})',
            }
        )
        keys_detail = wx_cli_state["keys_path"]
        if wx_cli_state["keys_exists"] and wx_cli_state["keys_entries"] is not None:
            keys_detail += f" ({wx_cli_state['keys_entries']} entries)"
        elif wx_cli_state["keys_parse_error"]:
            keys_detail += f" ({wx_cli_state['keys_parse_error']})"
        elif not wx_cli_state["keys_exists"]:
            keys_detail += " (missing)"
        report["checks"].append(
            {
                "name": "wx-cli all_keys.json",
                "ok": wx_cli_state["keys_exists"] and not wx_cli_state["keys_parse_error"],
                "detail": keys_detail,
            }
        )
        version_check = run_command([wx_path, "--version"])
        report["checks"].append(
            {
                "name": "wx --version",
                "ok": version_check["ok"],
                "detail": version_check["stdout"] or version_check["stderr"] or "no output",
            }
        )
        sessions_check = run_command([wx_path, "sessions", "--json"])
        sessions_detail = sessions_check["stdout"] or sessions_check["stderr"] or "no output"
        if sessions_check["ok"]:
            try:
                sessions_payload = json.loads(sessions_check["stdout"])
                if isinstance(sessions_payload, list):
                    sessions_count = len(sessions_payload)
                    sessions_detail = f"{sessions_count} sessions readable"
                else:
                    sessions_detail = "command succeeded but JSON was not a list"
                    sessions_check["ok"] = False
            except json.JSONDecodeError:
                sessions_detail = "command succeeded but stdout was not valid JSON"
                sessions_check["ok"] = False
        report["checks"].append(
            {
                "name": "wx sessions --json",
                "ok": sessions_check["ok"],
                "detail": sessions_detail,
            }
        )

    if not wx_path:
        report["next_steps"].extend(install_steps_for_missing_wx(platform_id))

    if wx_path and sessions_check and not sessions_check["ok"]:
        report["diagnostics"].extend(wx_cli_state.get("diagnostics", []))
        report["next_steps"].extend(
            recovery_steps_for_unreadable_sessions(platform_id, wx_bin, wx_cli_state)
        )
        report["next_steps"].append(manual_fallback_step(platform_id))

    if not state.get("config_path") and not state.get("baoyu_extend_path"):
        report["next_steps"].append(
            step(
                "Save a local data root for this repo",
                config_init_command(platform_id),
                "This repo can run without baoyu; local config keeps the data path reusable.",
            )
        )

    report["ready"] = bool(wx_path) and bool(version_check and version_check["ok"]) and bool(
        sessions_check and sessions_check["ok"]
    )
    return report


def print_text(report: dict[str, Any]) -> None:
    status = "ready" if report["ready"] else "action-needed"
    print(f"wx-summary-skill doctor: {status}")
    print(f"- project_root: {report['project_root']}")
    print(f"- platform: {report['platform_label']} ({report['platform']})")
    print(f"- python_command: {report['python_command']}")
    print(f"- wx_bin: {report['wx_bin']}")
    print(f"- wx_path: {report['wx_path'] or 'missing'}")
    for item in report["checks"]:
        marker = "ok" if item["ok"] else "fail"
        print(f"- {item['name']}: {marker} | {item['detail']}")
    state = report["state"]
    print(
        "- config_source: "
        + (state["config_path"] or state["baoyu_extend_path"] or "none (repo can still bootstrap)")
    )
    print(
        "- default_data_root: "
        + state["default_data_root"]
        + (" (exists)" if state["default_data_root_exists"] else " (will be created on first run)")
    )
    if report["diagnostics"]:
        print("")
        print("Diagnostics:")
        for item in report["diagnostics"]:
            print(f"- {item['code']}: {item['summary']}")
            print(f"  {item['detail']}")
    if report["next_steps"]:
        print("")
        print("Next steps:")
        for idx, item in enumerate(report["next_steps"], start=1):
            print(f"{idx}. {item['title']}")
            print(f"   {item['command']}")
            print(f"   {item['why']}")


def main() -> None:
    args = parse_args()
    report = build_report(project_root_from(args.project_root), args.platform)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report)
    raise SystemExit(0 if report["ready"] else 1)


if __name__ == "__main__":
    main()
