#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import py_compile
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from bootstrap_skill import bootstrap_report
from check_wechat_env import build_report
from newspaper_bridge import build_render_payload
from render_web_digest import render_html
from skill_state import DEFAULT_WEB_STYLE, inspect_payload


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_script_compilation() -> None:
    for script_path in sorted(SCRIPT_DIR.glob("*.py")):
        py_compile.compile(str(script_path), doraise=True)


def write_project_config(project_root: Path, wx_bin: str, data_root: str = "./wechat") -> Path:
    config_dir = project_root / ".wx-summary-skill"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    config_path.write_text(
        json.dumps({"data_root": data_root, "wx_bin": wx_bin}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return config_path


def write_upstream_wx_cli_config(home_dir: Path, db_dir: Path, keys_file: str = "all_keys.json") -> Path:
    cli_dir = home_dir / ".wx-cli"
    cli_dir.mkdir(parents=True, exist_ok=True)
    config_path = cli_dir / "config.json"
    config_path.write_text(
        json.dumps({"db_dir": str(db_dir), "keys_file": keys_file}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return config_path


def write_mock_wx(bin_dir: Path, mode: str) -> str:
    impl = bin_dir / "wx_mock_impl.py"
    impl.write_text(
        "\n".join(
            [
                "import sys",
                f"MODE = {mode!r}",
                "args = sys.argv[1:]",
                "if args == ['--version']:",
                "    print('wx 0.0-test')",
                "    raise SystemExit(0)",
                "if args == ['sessions', '--json']:",
                "    if MODE == 'ok':",
                "        print('[]')",
                "        raise SystemExit(0)",
                "    print('mock sessions failure', file=sys.stderr)",
                "    raise SystemExit(2)",
                "print('unsupported mock args', file=sys.stderr)",
                "raise SystemExit(3)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    if os.name == "nt":
        wrapper = bin_dir / "wx-mock.cmd"
        wrapper.write_text(f'@echo off\r\n"{sys.executable}" "{impl}" %*\r\n', encoding="utf-8")
    else:
        wrapper = bin_dir / "wx-mock"
        wrapper.write_text(
            "\n".join(
                [
                    "#!/bin/sh",
                    f'exec "{sys.executable}" "{impl}" "$@"',
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
    return "wx-mock"


def test_missing_wx_install_steps() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        write_project_config(project_root, "wx-missing")
        windows = build_report(project_root, "win32")
        linux = build_report(project_root, "linux")
        assert_true(windows["python_command"] == "py -3", "Windows should prefer py -3")
        assert_true(
            any("install.ps1" in step["command"] for step in windows["next_steps"]),
            "Windows doctor should recommend install.ps1",
        )
        assert_true(
            any("install.sh" in step["command"] for step in linux["next_steps"]),
            "Linux doctor should recommend install.sh",
        )


def test_platform_specific_recovery_steps() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        wx_bin = write_mock_wx(bin_dir, "fail")
        write_project_config(root, wx_bin)
        original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(bin_dir) + os.pathsep + original_path
        try:
            windows = build_report(root, "win32")
            linux = build_report(root, "linux")
            macos = build_report(root, "darwin")
        finally:
            os.environ["PATH"] = original_path
        assert_true(
            any(step["command"] == "Start-Process PowerShell -Verb RunAs" for step in windows["next_steps"]),
            "Windows recovery should ask for elevated PowerShell",
        )
        assert_true(
            any(step["command"] == f"{wx_bin} init" for step in windows["next_steps"]),
            "Windows recovery should include wx init",
        )
        assert_true(
            any(step["command"] == f"sudo {wx_bin} init" for step in linux["next_steps"]),
            "Linux recovery should include sudo wx init",
        )
        assert_true(
            any("codesign" in step["command"] for step in macos["next_steps"]),
            "macOS recovery should mention codesign",
        )


def test_bootstrap_creates_config_when_missing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        report = bootstrap_report(
            SimpleNamespace(
                project_root=str(project_root),
                scope="project",
                data_root=None,
                wx_bin="wx-missing",
                self_wxid=None,
                self_display=None,
                no_init_config=False,
                force_init_config=False,
                platform="win32",
                json=False,
            )
        )
        config_path = project_root / ".wx-summary-skill" / "config.json"
        assert_true(report["config_action"] == "created", "Bootstrap should create config")
        assert_true(config_path.exists(), "Bootstrap should write project config")
        assert_true(
            Path(report["config_path"]).resolve() == config_path.resolve(),
            "Bootstrap should report config path",
        )
        assert_true(report["ready"] is False, "Bootstrap should stay non-ready when wx is missing")


def test_windows_last_mile_diagnostics() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        wx_bin = write_mock_wx(bin_dir, "fail")
        write_project_config(root, wx_bin)

        home_dir = root / "home"
        home_dir.mkdir()
        appdata_dir = root / "appdata"
        ini_dir = appdata_dir / "Tencent" / "xwechat" / "config"
        ini_dir.mkdir(parents=True, exist_ok=True)

        configured_db_dir = root / "manual-data" / "xwechat_files" / "wxid_manual" / "db_storage"
        configured_db_dir.mkdir(parents=True, exist_ok=True)
        (configured_db_dir / "session.db").write_bytes(b"sqlite")
        write_upstream_wx_cli_config(home_dir, configured_db_dir)

        detected_root = root / "migrated-data"
        detected_db_dir = detected_root / "xwechat_files" / "wxid_detected" / "db_storage"
        detected_db_dir.mkdir(parents=True, exist_ok=True)
        (detected_db_dir / "message_0.db").write_bytes(b"sqlite")
        (ini_dir / "account.ini").write_text(str(detected_root) + "\n", encoding="utf-8")

        original_path = os.environ.get("PATH", "")
        original_home = os.environ.get("HOME")
        original_userprofile = os.environ.get("USERPROFILE")
        original_appdata = os.environ.get("APPDATA")
        os.environ["PATH"] = str(bin_dir) + os.pathsep + original_path
        os.environ["HOME"] = str(home_dir)
        # On real Windows runners, Path.home() resolves from USERPROFILE/HOMEDRIVE/HOMEPATH,
        # not HOME, so the selftest must override USERPROFILE to point at the temp fixture.
        os.environ["USERPROFILE"] = str(home_dir)
        os.environ["APPDATA"] = str(appdata_dir)
        try:
            report = build_report(root, "win32")
        finally:
            os.environ["PATH"] = original_path
            if original_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = original_home
            if original_userprofile is None:
                os.environ.pop("USERPROFILE", None)
            else:
                os.environ["USERPROFILE"] = original_userprofile
            if original_appdata is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = original_appdata

        codes = {item["code"] for item in report["diagnostics"]}
        assert_true(
            "windows_wx_init_reautodetects_before_keys" in codes,
            "Windows doctor should explain wx init re-autodetect behavior when keys are missing",
        )
        assert_true(
            "windows_configured_db_dir_outside_autodetect" in codes,
            "Windows doctor should flag configured db_dir values that are outside auto-detect candidates",
        )
        assert_true(
            any(step["title"] == "Inspect WeChat data-root hints" for step in report["next_steps"]),
            "Windows doctor should suggest checking %APPDATA% xwechat ini hints",
        )


def test_default_web_style_prefers_newspaper_mode() -> None:
    assert_true(
        DEFAULT_WEB_STYLE == "people-daily-v1",
        "Default webpage style should point to the newspaper mode",
    )
    with tempfile.TemporaryDirectory() as tmp:
        payload = inspect_payload(Path(tmp))
    assert_true(
        payload["style_options"]["webpage"][0]["id"] == "people-daily-v1",
        "Inspect payload should expose the newspaper webpage style",
    )


def test_render_html_uses_newspaper_layout() -> None:
    summary = {
        "group_name": "IGN AI | 洋来",
        "group_id": "43663749608@chatroom",
        "time_range": "2026-05-12 ~ 2026-05-18",
        "headline": "工具混战里长出一张学生 Builder 前台",
        "subheadline": "这周讨论主要围绕登录、预算、工具栈和线下活动展开。",
        "opening": "这一版把群里最有代表性的几条工作流线索压成头版 lead，保留讨论节奏，也保留判断。",
        "period_in_one_line": "这一周的重心不是追新模型，而是把可用工作流稳下来。",
        "main_threads": [
            {
                "title": "工具选择从品牌崇拜退回场景判断",
                "summary": "群里不断把 Codex、Claude、Trae、豆包重新放回不同使用场景里比较。",
            },
            {
                "title": "登录和中转站问题被拆成独立资源层",
                "summary": "这条线把账号、refresh token、接码和中转站从“模型能力”里剥离出来。",
            },
        ],
        "people": [{"name": "千逐", "tag": "主持判断", "desc": "多次把抽象争论压回真实场景。"}],
        "timeline": [{"date": "05-15", "label": "周五", "bullets": ["集中讨论登录、会话和客户端迁移。"]}],
        "quotes": [{"text": "先按任务选，不要先按信仰选。", "who": "千逐"}],
        "links": [{"title": "Codex", "note": "作为开发协作主场景不断被提及。"}],
        "next_actions": ["下一版可以继续追线下活动和设备预算这两条线。"],
    }
    analysis = {
        "total_messages": 128,
        "active_senders": 19,
        "char_count": 11243,
        "top_senders": [{"name": "千逐", "count": 24}, {"name": "管家", "count": 18}],
        "peak_day": {"date": "2026-05-15", "count": 41},
        "last_message_time": "2026-05-18 22:11",
        "date_range": {"since": "2026-05-12", "until": "2026-05-18"},
    }
    html = render_html(summary, analysis)
    assert_true("头 版 要 闻" in html, "Rendered HTML should render the newspaper front page")
    assert_true(
        "第 1 版 / 共 4 版" in html,
        "Rendered HTML should expose multi-page newspaper page furniture",
    )
    assert_true("群聊信息报 / Chat Digest" not in html, "Legacy card-digest masthead should be gone")
    assert_true("APPENDIX" in html, "Rendered HTML should include the appendix page from the newspaper layout")


def test_render_payload_supports_optional_branding() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        group_dir = root / "wechat" / "example-group"
        branding_dir = group_dir / "branding"
        run_dir = group_dir / "newspaper" / "preview"
        branding_dir.mkdir(parents=True, exist_ok=True)

        Image.new("RGB", (256, 256), "#24406a").save(branding_dir / "site-icon.png", format="PNG")
        (branding_dir / "site-branding.json").write_text(
            json.dumps({"theme_color": "#24406a"}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        summary = {
            "group_name": "IGN AI | 洋来",
            "group_id": "43663749608@chatroom",
            "time_range": "2026-05-12 ~ 2026-05-18",
            "headline": "工具混战里长出一张学生 Builder 前台",
            "subheadline": "这周讨论主要围绕登录、预算、工具栈和线下活动展开。",
            "opening": "这一版把群里最有代表性的几条工作流线索压成头版 lead，保留讨论节奏，也保留判断。",
            "period_in_one_line": "这一周的重心不是追新模型，而是把可用工作流稳下来。",
            "main_threads": [{"title": "工具判断", "summary": "把工具放回真实场景里比较。"}],
            "people": [{"name": "千逐", "tag": "主持判断", "desc": "多次把抽象争论压回真实场景。"}],
            "timeline": [{"date": "05-15", "label": "周五", "bullets": ["集中讨论登录、会话和客户端迁移。"]}],
            "quotes": [{"text": "先按任务选，不要先按信仰选。", "who": "千逐"}],
            "links": [{"title": "Codex", "note": "作为开发协作主场景不断被提及。"}],
            "next_actions": ["下一版可以继续追线下活动和设备预算这两条线。"],
        }
        analysis = {
            "total_messages": 128,
            "active_senders": 19,
            "char_count": 11243,
            "top_senders": [{"name": "千逐", "count": 24}, {"name": "管家", "count": 18}],
            "peak_day": {"date": "2026-05-15", "count": 41},
            "last_message_time": "2026-05-18 22:11",
            "date_range": {"since": "2026-05-12", "until": "2026-05-18"},
        }

        result = build_render_payload(summary, analysis, group_dir, run_dir)
        html = Path(result["site_index"]).read_text(encoding="utf-8")
        dist_html = Path(result["dist_index"]).read_text(encoding="utf-8")

        assert_true('name="theme-color" content="#24406a"' in html, "Branding should inject theme-color into site HTML")
        assert_true('href="./favicon.ico"' in html, "Branding should inject favicon link into site HTML")
        assert_true('href="./apple-touch-icon.png"' in html, "Branding should inject apple-touch icon into site HTML")
        assert_true('href="./favicon.ico"' in dist_html, "Dist HTML should keep the injected favicon links")

        for rel_path in (
            "favicon.ico",
            "favicon-16x16.png",
            "favicon-32x32.png",
            "apple-touch-icon.png",
            "site-icon-512.png",
        ):
            assert_true((run_dir / "site" / rel_path).exists(), f"Site output should include {rel_path}")
            assert_true((run_dir / "dist" / rel_path).exists(), f"Dist output should include {rel_path}")


def main() -> None:
    test_script_compilation()
    test_missing_wx_install_steps()
    test_platform_specific_recovery_steps()
    test_bootstrap_creates_config_when_missing()
    test_windows_last_mile_diagnostics()
    test_default_web_style_prefers_newspaper_mode()
    test_render_html_uses_newspaper_layout()
    test_render_payload_supports_optional_branding()
    print("selftest_repo.py: all checks passed")


if __name__ == "__main__":
    main()
