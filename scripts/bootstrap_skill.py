#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from types import SimpleNamespace
from typing import Any

from check_wechat_env import build_report, normalized_platform, platform_label, python_command
from skill_state import init_config, merge_state, project_root_from


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap wx-summary-skill for direct GitHub clone users."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--scope", choices=["project", "xdg", "home"], default="project")
    parser.add_argument("--data-root", help="Override repo-native data_root.")
    parser.add_argument("--wx-bin", help="Override wx binary name/path stored in config.")
    parser.add_argument("--self-wxid")
    parser.add_argument("--self-display")
    parser.add_argument(
        "--no-init-config",
        action="store_true",
        help="Do not auto-create repo-native config when none exists.",
    )
    parser.add_argument(
        "--force-init-config",
        action="store_true",
        help="Always rewrite repo-native config with the provided bootstrap values.",
    )
    parser.add_argument(
        "--platform",
        help="Override detected platform for smoke tests or docs validation (darwin/linux/win32).",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON instead of human text.")
    return parser.parse_args()


def default_data_root(platform_id: str) -> str:
    return ".\\wechat" if platform_id == "win32" else "./wechat"


def bootstrap_report(args: argparse.Namespace) -> dict[str, Any]:
    project_root = project_root_from(args.project_root)
    platform_id = normalized_platform(args.platform)
    merged_before = merge_state(project_root)

    config_action = "unchanged"
    config_result: dict[str, Any] | None = None
    source = "none"

    if merged_before.get("config_path"):
        source = "repo-native"
    elif merged_before.get("baoyu_extend_path"):
        source = "baoyu"

    should_init = args.force_init_config or (
        not args.no_init_config
        and not merged_before.get("config_path")
        and not merged_before.get("baoyu_extend_path")
    )

    if should_init:
        config_args = SimpleNamespace(
            project_root=str(project_root),
            scope=args.scope,
            data_root=args.data_root or default_data_root(platform_id),
            self_wxid=args.self_wxid,
            self_display=args.self_display,
            wx_bin=args.wx_bin,
        )
        config_result = init_config(config_args)
        config_action = "updated" if merged_before.get("config_path") else "created"
        source = "repo-native"

    merged_after = merge_state(project_root)
    doctor = build_report(project_root, args.platform)

    ready_command = "$wx-summary-skill"
    if platform_id == "win32":
        quickstart = f'py -3 scripts/bootstrap_skill.py --project-root "{project_root}"'
    else:
        quickstart = f'python3 scripts/bootstrap_skill.py --project-root "{project_root}"'

    return {
        "project_root": str(project_root),
        "platform": platform_id,
        "platform_label": platform_label(platform_id),
        "python_command": python_command(platform_id),
        "config_action": config_action,
        "config_source": source,
        "config_result": config_result,
        "config_path": merged_after.get("config_path"),
        "baoyu_extend_path": merged_after.get("baoyu_extend_path"),
        "ready": doctor["ready"],
        "doctor": doctor,
        "next_commands": {
            "bootstrap": quickstart,
            "invoke_skill": ready_command,
        },
    }


def print_text(report: dict[str, Any]) -> None:
    status = "ready" if report["ready"] else "action-needed"
    print(f"wx-summary-skill bootstrap: {status}")
    print(f"- project_root: {report['project_root']}")
    print(f"- platform: {report['platform_label']} ({report['platform']})")
    print(f"- python_command: {report['python_command']}")
    print(f"- config_source: {report['config_source']}")
    print(f"- config_action: {report['config_action']}")
    print(f"- config_path: {report['config_path'] or 'none'}")
    if report["baoyu_extend_path"]:
        print(f"- baoyu_extend_path: {report['baoyu_extend_path']}")

    doctor = report["doctor"]
    print(f"- wx_bin: {doctor['wx_bin']}")
    print(f"- wx_path: {doctor['wx_path'] or 'missing'}")
    for item in doctor["checks"]:
        marker = "ok" if item["ok"] else "fail"
        print(f"- {item['name']}: {marker} | {item['detail']}")

    if report["ready"]:
        print("")
        print("Next command:")
        print(f"1. {report['next_commands']['invoke_skill']}")
        print("   Start the interactive group summary workflow.")
        return

    if doctor["next_steps"]:
        print("")
        print("Next steps:")
        for idx, item in enumerate(doctor["next_steps"], start=1):
            print(f"{idx}. {item['title']}")
            print(f"   {item['command']}")
            print(f"   {item['why']}")


def main() -> None:
    args = parse_args()
    report = bootstrap_report(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report)
    raise SystemExit(0 if report["ready"] else 1)


if __name__ == "__main__":
    main()
