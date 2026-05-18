#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import py_compile
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from bootstrap_skill import bootstrap_report
from check_wechat_env import build_report


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


def main() -> None:
    test_script_compilation()
    test_missing_wx_install_steps()
    test_platform_specific_recovery_steps()
    test_bootstrap_creates_config_when_missing()
    print("selftest_repo.py: all checks passed")


if __name__ == "__main__":
    main()
