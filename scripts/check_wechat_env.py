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


def build_report(project_root: Path) -> dict[str, Any]:
    state = inspect_payload(project_root)
    resolved = state["state"]
    default_data_root = Path(resolved["default_data_root"]).expanduser()
    wx_bin = state.get("resolved_defaults", {}).get("wx_bin") or "wx"
    wx_path = shutil.which(wx_bin)

    report: dict[str, Any] = {
        "project_root": str(project_root),
        "ready": False,
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
        report["next_steps"].extend(
            [
                step(
                    "Install wx-cli with npm",
                    "npm install -g @jackwener/wx-cli",
                    "Official install path when you already have Node.js / npm.",
                ),
                step(
                    "Install wx-cli with the official script",
                    "curl -fsSL https://raw.githubusercontent.com/jackwener/wx-cli/main/install.sh | bash",
                    "Fast path if you do not want to set up npm first.",
                ),
                step(
                    "Optional: add the upstream wx-cli skill",
                    "npx skills add jackwener/wx-cli -g",
                    "Useful if you also want a standalone skill around wx-cli itself.",
                ),
            ]
        )

    if wx_path and sessions_check and not sessions_check["ok"] and sys.platform == "darwin":
        report["next_steps"].extend(
            [
                step(
                    "Re-sign WeChat",
                    "sudo codesign --force --deep --sign - /Applications/WeChat.app",
                    "wx-cli needs the default macOS WeChat app to be re-signed before initialization.",
                ),
                step(
                    "Restart WeChat",
                    "open -a WeChat",
                    "After codesign, reopen WeChat and make sure your account is logged in.",
                ),
                step(
                    "Initialize wx-cli",
                    "sudo wx init",
                    "This prepares the accessibility / injection layer used by wx-cli on macOS.",
                ),
                step(
                    "Verify readable sessions",
                    "wx sessions --json",
                    "You should see JSON output before running wx-summary-skill.",
                ),
            ]
        )

    if not state.get("config_path") and not state.get("baoyu_extend_path"):
        report["next_steps"].append(
            step(
                "Save a local data root for this repo",
                "python3 scripts/skill_state.py init-config --scope project --data-root ./wechat",
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
    report = build_report(project_root_from(args.project_root))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report)
    raise SystemExit(0 if report["ready"] else 1)


if __name__ == "__main__":
    main()
