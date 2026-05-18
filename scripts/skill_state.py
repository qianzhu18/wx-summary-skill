#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_RECENT_GROUPS = 8
DEFAULT_TEXT_STYLE = "growth-brief-v1"
DEFAULT_WEB_STYLE = "daily-report-v1"
DEFAULT_WX_BIN = "wx"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage wx-summary-skill local state.")
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root used for project-scoped config and default data_root.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("inspect", help="Print merged state and available choices.")

    save_parser = subparsers.add_parser("save-session", help="Persist recent group and defaults.")
    save_parser.add_argument("--scope", choices=["project", "xdg", "home"], default="project")
    save_parser.add_argument("--group-id")
    save_parser.add_argument("--group-name")
    save_parser.add_argument("--duration-preset")
    save_parser.add_argument("--summary-mode", choices=["text", "webpage"])
    save_parser.add_argument("--text-style")
    save_parser.add_argument("--web-style")
    save_parser.add_argument("--data-root")

    config_parser = subparsers.add_parser(
        "init-config",
        help="Create or update repo-native config for users who do not use baoyu defaults.",
    )
    config_parser.add_argument("--scope", choices=["project", "xdg", "home"], default="project")
    config_parser.add_argument("--data-root")
    config_parser.add_argument("--self-wxid")
    config_parser.add_argument("--self-display")
    config_parser.add_argument("--wx-bin")
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def project_root_from(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve()


def xdg_config_home() -> Path:
    return Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")).expanduser().resolve()


def write_targets(project_root: Path) -> dict[str, Path]:
    return {
        "project": project_root / ".wx-summary-skill" / "state.json",
        "xdg": xdg_config_home() / "wx-summary-skill" / "state.json",
        "home": Path.home().resolve() / ".wx-summary-skill" / "state.json",
    }


def config_targets(project_root: Path) -> dict[str, Path]:
    return {
        "project": project_root / ".wx-summary-skill" / "config.json",
        "xdg": xdg_config_home() / "wx-summary-skill" / "config.json",
        "home": Path.home().resolve() / ".wx-summary-skill" / "config.json",
    }


def baoyu_extend_candidates(project_root: Path) -> list[Path]:
    return [
        project_root / ".baoyu-skills" / "baoyu-wechat-summary" / "EXTEND.md",
        xdg_config_home() / "baoyu-skills" / "baoyu-wechat-summary" / "EXTEND.md",
        Path.home().resolve() / ".baoyu-skills" / "baoyu-wechat-summary" / "EXTEND.md",
    ]


def load_simple_kv(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, value = line.split(":", 1)
        elif "=" in line:
            key, value = line.split("=", 1)
        else:
            continue
        data[key.strip().lower()] = value.strip()
    return data


def load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"expected JSON object in {path}")
    return payload


def load_baoyu_defaults(project_root: Path) -> tuple[dict[str, Any], str | None]:
    for candidate in baoyu_extend_candidates(project_root):
        if candidate.exists():
            data = load_simple_kv(candidate)
            return (
                {
                    "self_wxid": data.get("self_wxid"),
                    "self_display": data.get("self_display"),
                    "data_root": data.get("data_root"),
                },
                str(candidate),
            )
    return ({}, None)


def normalize_skill_config(data: Any) -> dict[str, str]:
    if not isinstance(data, dict):
        return {}
    normalized: dict[str, str] = {}
    for key in ["self_wxid", "self_display", "data_root", "wx_bin"]:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            normalized[key] = text
    return normalized


def load_skill_config(project_root: Path) -> tuple[dict[str, str], str | None]:
    for candidate in config_targets(project_root).values():
        if candidate.exists():
            return normalize_skill_config(load_json_object(candidate)), str(candidate)
    return ({}, None)


def default_state(project_root: Path, skill_defaults: dict[str, Any]) -> dict[str, Any]:
    return {
        "default_duration_preset": "1d",
        "default_summary_mode": "text",
        "default_text_style": DEFAULT_TEXT_STYLE,
        "default_web_style": DEFAULT_WEB_STYLE,
        "default_data_root": skill_defaults.get("data_root") or str(project_root / "wechat"),
        "recent_groups": [],
    }


def load_existing_state(project_root: Path) -> tuple[dict[str, Any], str | None]:
    for candidate in write_targets(project_root).values():
        if candidate.exists():
            data = load_json_object(candidate)
            return data, str(candidate)
    return ({}, None)


def normalize_recent_groups(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        group_id = str(item.get("group_id") or "").strip()
        group_name = str(item.get("group_name") or "").strip()
        key = (group_id, group_name)
        if key == ("", "") or key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "group_id": group_id,
                "group_name": group_name,
                "last_used_at": str(item.get("last_used_at") or ""),
            }
        )
    return normalized[:MAX_RECENT_GROUPS]


def merge_state(project_root: Path) -> dict[str, Any]:
    baoyu_defaults, baoyu_path = load_baoyu_defaults(project_root)
    skill_config, skill_config_path = load_skill_config(project_root)
    merged_defaults = {
        "self_wxid": skill_config.get("self_wxid") or baoyu_defaults.get("self_wxid"),
        "self_display": skill_config.get("self_display") or baoyu_defaults.get("self_display"),
        "data_root": skill_config.get("data_root") or baoyu_defaults.get("data_root"),
        "wx_bin": skill_config.get("wx_bin") or DEFAULT_WX_BIN,
    }
    existing_state, state_path = load_existing_state(project_root)
    merged = default_state(project_root, merged_defaults)
    merged.update(
        {
            "default_duration_preset": existing_state.get(
                "default_duration_preset", merged["default_duration_preset"]
            ),
            "default_summary_mode": existing_state.get(
                "default_summary_mode", merged["default_summary_mode"]
            ),
            "default_text_style": existing_state.get(
                "default_text_style", merged["default_text_style"]
            ),
            "default_web_style": existing_state.get(
                "default_web_style", merged["default_web_style"]
            ),
            "default_data_root": existing_state.get(
                "default_data_root", merged["default_data_root"]
            ),
            "recent_groups": normalize_recent_groups(existing_state.get("recent_groups", [])),
        }
    )
    return {
        "project_root": str(project_root),
        "state_path": state_path,
        "state_exists": bool(state_path),
        "write_targets": {key: str(value) for key, value in write_targets(project_root).items()},
        "config_path": skill_config_path,
        "config_exists": bool(skill_config_path),
        "config_targets": {key: str(value) for key, value in config_targets(project_root).items()},
        "skill_config": skill_config,
        "baoyu_extend_path": baoyu_path,
        "baoyu_defaults": baoyu_defaults,
        "resolved_defaults": merged_defaults,
        "state": merged,
    }


def recent_group_choices(recent_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    choices = [
        {
            "id": f"recent:{item['group_id'] or item['group_name']}",
            "group_id": item["group_id"],
            "group_name": item["group_name"],
            "label": item["group_name"] or item["group_id"],
            "source": "recent",
        }
        for item in recent_groups
    ]
    choices.append({"id": "other", "label": "Other", "source": "manual"})
    return choices


def inspect_payload(project_root: Path) -> dict[str, Any]:
    merged = merge_state(project_root)
    state = merged["state"]
    payload = {
        **merged,
        "recent_group_choices": recent_group_choices(state["recent_groups"]),
        "duration_presets": [
            {"id": "1d", "label": "1 天"},
            {"id": "3d", "label": "3 天"},
            {"id": "7d", "label": "1 周"},
            {"id": "14d", "label": "2 周"},
            {"id": "30d", "label": "1 个月"},
            {"id": "custom", "label": "自定义"},
        ],
        "summary_modes": [
            {"id": "text", "label": "文字总结"},
            {"id": "webpage", "label": "网页信息报"},
        ],
        "style_options": {
            "text": [{"id": DEFAULT_TEXT_STYLE, "label": "默认文字总结样式"}],
            "webpage": [{"id": DEFAULT_WEB_STYLE, "label": "默认网页信息报样式"}],
        },
    }
    return payload


def upsert_recent_group(recent_groups: list[dict[str, Any]], group_id: str, group_name: str) -> list[dict[str, Any]]:
    normalized = [
        item
        for item in recent_groups
        if not (
            (group_id and item.get("group_id") == group_id)
            or (group_name and item.get("group_name") == group_name)
        )
    ]
    normalized.insert(
        0,
        {
            "group_id": group_id,
            "group_name": group_name,
            "last_used_at": now_iso(),
        },
    )
    return normalized[:MAX_RECENT_GROUPS]


def save_session(args: argparse.Namespace) -> dict[str, Any]:
    project_root = project_root_from(args.project_root)
    merged = merge_state(project_root)
    state = merged["state"]
    if args.duration_preset:
        state["default_duration_preset"] = args.duration_preset
    if args.summary_mode:
        state["default_summary_mode"] = args.summary_mode
    if args.text_style:
        state["default_text_style"] = args.text_style
    if args.web_style:
        state["default_web_style"] = args.web_style
    if args.data_root:
        state["default_data_root"] = args.data_root
    if args.group_id or args.group_name:
        state["recent_groups"] = upsert_recent_group(
            state["recent_groups"],
            args.group_id or "",
            args.group_name or "",
        )

    target = write_targets(project_root)[args.scope]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "saved_to": str(target),
        "state": state,
    }


def init_config(args: argparse.Namespace) -> dict[str, Any]:
    project_root = project_root_from(args.project_root)
    merged = merge_state(project_root)
    config = {
        **merged["skill_config"],
        **{
            "data_root": args.data_root or merged["resolved_defaults"].get("data_root") or str(project_root / "wechat"),
            "wx_bin": args.wx_bin or merged["resolved_defaults"].get("wx_bin") or DEFAULT_WX_BIN,
        },
    }
    if args.self_wxid:
        config["self_wxid"] = args.self_wxid.strip()
    if args.self_display:
        config["self_display"] = args.self_display.strip()

    target = config_targets(project_root)[args.scope]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "saved_to": str(target),
        "config": config,
    }


def main() -> None:
    args = parse_args()
    project_root = project_root_from(args.project_root)
    if args.command == "inspect":
        print(json.dumps(inspect_payload(project_root), ensure_ascii=False, indent=2))
        return
    if args.command == "save-session":
        print(json.dumps(save_session(args), ensure_ascii=False, indent=2))
        return
    if args.command == "init-config":
        print(json.dumps(init_config(args), ensure_ascii=False, indent=2))
        return
    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
