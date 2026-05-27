#!/usr/bin/env python3
"""Deploy IGN AI daily reports to the self-hosted publisher.

Deploys each daily report as a separate site under the /community/ignai/DP/ path.

Usage:
  python deploy_ignai_daily.py --dist-dir /path/to/dist --deploy-all
  python deploy_ignai_daily.py --dist-dir /path/to/dist --date 2026-05-26
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

import requests


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if not slug:
        raise ValueError("slug cannot be empty")
    return slug


def get_env() -> tuple[str, str, str]:
    base_url = os.environ.get("WECHAT_PUBLISHER_URL", "http://107.174.53.171:8787")
    token = os.environ.get("WECHAT_PUBLISHER_TOKEN", "")
    public_base = os.environ.get("WECHAT_REPORT_PUBLIC_BASE_URL", "https://qianzhu.online/community")
    if not token:
        # Try loading from env file
        env_file = Path.home() / ".config" / "wechat-weekly-report" / "publisher.env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith("export "):
                    line = line[7:]
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k == "WECHAT_PUBLISHER_URL":
                        base_url = v
                    elif k == "WECHAT_PUBLISHER_TOKEN":
                        token = v
                    elif k == "WECHAT_REPORT_PUBLIC_BASE_URL":
                        public_base = v
    return base_url, token, public_base


def ensure_site(base_url: str, token: str, slug: str, title: str, public_path: str) -> bool:
    headers = {"x-deploy-token": token}
    payload = {
        "slug": slug,
        "title": title,
        "public_base_url": "https://qianzhu.online/community",
        "public_path": public_path,
    }
    try:
        resp = requests.post(f"{base_url}/api/sites", headers=headers, json=payload, timeout=30)
        if resp.status_code == 409:
            return True
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"  Warning: ensure_site failed: {e}")
        return False


def deploy_zip(base_url: str, token: str, slug: str, zip_path: Path) -> dict:
    headers = {"x-deploy-token": token}
    with open(zip_path, "rb") as f:
        resp = requests.post(
            f"{base_url}/api/sites/{slug}/deploy",
            headers=headers,
            files={"archive": (zip_path.name, f, "application/zip")},
            timeout=60,
        )
    resp.raise_for_status()
    return resp.json()


def zip_file(html_path: Path) -> Path:
    """Create a zip containing the HTML as index.html."""
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(html_path, "site/index.html")
    return Path(tmp.name)


def deploy_single(base_url: str, token: str, public_base: str, html_path: Path, date_str: str) -> bool:
    """Deploy a single daily report."""
    # Slug: ignai-dp-2026-05-26
    slug = f"ignai-dp-{date_str}"
    # Public path: /ignai/DP/2026-05-26/
    public_path = f"/ignai/DP/{date_str}/"
    title = f"IGN AI 日报 {date_str}"

    print(f"  Deploying {date_str} -> {slug}")

    # Ensure site exists
    ensure_site(base_url, token, slug, title, public_path)

    # Zip and deploy
    zip_path = zip_file(html_path)
    try:
        result = deploy_zip(base_url, token, slug, zip_path)
        print(f"  Success: {result.get('url', 'deployed')}")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False
    finally:
        zip_path.unlink(missing_ok=True)


def deploy_archive(base_url: str, token: str, public_base: str, index_path: Path) -> bool:
    """Deploy the archive index page."""
    slug = "ignai-daily-archive"
    public_path = "/ignai/DP/"
    title = "IGN AI 日报档案"

    print(f"  Deploying archive index -> {slug}")
    ensure_site(base_url, token, slug, title, public_path)

    zip_path = zip_file(index_path)
    try:
        result = deploy_zip(base_url, token, slug, zip_path)
        print(f"  Success: {result.get('url', 'deployed')}")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False
    finally:
        zip_path.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Deploy IGN AI daily reports")
    p.add_argument("--dist-dir", required=True, help="Path to dist directory")
    p.add_argument("--date", help="Deploy specific date only")
    p.add_argument("--deploy-all", action="store_true", help="Deploy all daily reports")
    p.add_argument("--archive-only", action="store_true", help="Deploy only the archive index")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    dist_dir = Path(args.dist_dir).expanduser().resolve()
    base_url, token, public_base = get_env()

    if not token:
        print("Error: WECHAT_PUBLISHER_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    print(f"Publisher: {base_url}")
    print(f"Public base: {public_base}")

    if args.archive_only:
        index_path = dist_dir / "index.html"
        if index_path.exists():
            deploy_archive(base_url, token, public_base, index_path)
        else:
            print("Error: index.html not found in dist dir")
        return

    if args.date:
        html_path = dist_dir / f"ignai-daily-{args.date}.html"
        if not html_path.exists():
            print(f"Error: {html_path} not found")
            sys.exit(1)
        deploy_single(base_url, token, public_base, html_path, args.date)
        return

    if args.deploy_all:
        # Deploy all daily reports
        daily_files = sorted(dist_dir.glob("ignai-daily-*.html"))
        print(f"\nDeploying {len(daily_files)} daily reports...")

        success = 0
        for f in daily_files:
            date_str = f.stem.replace("ignai-daily-", "")
            if deploy_single(base_url, token, public_base, f, date_str):
                success += 1

        print(f"\nDeployed {success}/{len(daily_files)} reports")

        # Also deploy archive index
        index_path = dist_dir / "index.html"
        if index_path.exists():
            print("\nDeploying archive index...")
            deploy_archive(base_url, token, public_base, index_path)

        return

    print("Specify --deploy-all, --date YYYY-MM-DD, or --archive-only")


if __name__ == "__main__":
    main()
