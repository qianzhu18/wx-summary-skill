#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
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


def recovery_steps_for_unreadable_sessions(platform_id: str, wx_bin: str) -> list[dict[str, str]]:
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
        return [
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

    if wx_path:
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
        report["next_steps"].extend(recovery_steps_for_unreadable_sessions(platform_id, wx_bin))

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
