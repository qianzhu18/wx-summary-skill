#!/usr/bin/env python3

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


BRANDING_DIR = "branding"
BRANDING_CONFIG = "site-branding.json"
ICON_CANDIDATES = (
    "site-icon.png",
    "site-icon.jpg",
    "site-icon.jpeg",
    "site-icon.webp",
)
RESAMPLING = getattr(Image, "Resampling", Image).LANCZOS


def _load_config(group_dir: Path) -> dict[str, Any]:
    path = group_dir / BRANDING_DIR / BRANDING_CONFIG
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _resolve_icon_source(group_dir: Path, config: dict[str, Any]) -> Path | None:
    configured = str(config.get("icon_source") or "").strip()
    candidates: list[Path] = []
    if configured:
        path = Path(configured).expanduser()
        candidates.append(path if path.is_absolute() else group_dir / path)
    branding_dir = group_dir / BRANDING_DIR
    candidates.extend(branding_dir / name for name in ICON_CANDIDATES)
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


def _square_icon(source: Path, size: int) -> Image.Image:
    image = Image.open(source).convert("RGBA")
    fitted = ImageOps.contain(image, (size, size), RESAMPLING)
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    x = (size - fitted.width) // 2
    y = (size - fitted.height) // 2
    canvas.paste(fitted, (x, y), fitted)
    return canvas


def _mime_type(url: str) -> str:
    lower = url.lower()
    if lower.endswith(".ico"):
        return "image/x-icon"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def _public_url(config: dict[str, Any], key: str) -> str:
    return str(config.get(key) or "").strip()


def build_branding_head(group_dir: Path, site_dir: Path) -> str:
    config = _load_config(group_dir)
    icon_source = _resolve_icon_source(group_dir, config)
    generated: dict[str, str] = {}
    if icon_source:
        site_dir.mkdir(parents=True, exist_ok=True)
        icon_512 = _square_icon(icon_source, 512)
        icon_180 = _square_icon(icon_source, 180)
        icon_32 = _square_icon(icon_source, 32)
        icon_16 = _square_icon(icon_source, 16)
        icon_512.save(site_dir / "site-icon-512.png", format="PNG")
        icon_180.save(site_dir / "apple-touch-icon.png", format="PNG")
        icon_32.save(site_dir / "favicon-32x32.png", format="PNG")
        icon_16.save(site_dir / "favicon-16x16.png", format="PNG")
        icon_512.save(
            site_dir / "favicon.ico",
            format="ICO",
            sizes=[(16, 16), (32, 32), (48, 48)],
        )
        generated = {
            "favicon_ico": "./favicon.ico",
            "favicon_16": "./favicon-16x16.png",
            "favicon_png": "./favicon-32x32.png",
            "apple_touch_icon": "./apple-touch-icon.png",
            "share_image": "./site-icon-512.png",
        }

    icon_url = _public_url(config, "icon_public_url") or generated.get("favicon_png") or generated.get("favicon_ico", "")
    apple_touch_icon_url = (
        _public_url(config, "apple_touch_icon_public_url")
        or generated.get("apple_touch_icon")
        or icon_url
    )
    share_image_url = _public_url(config, "og_image_public_url") or generated.get("share_image", "")
    theme_color = str(config.get("theme_color") or "").strip()

    lines: list[str] = []
    if theme_color:
        lines.append(f'<meta name="theme-color" content="{html.escape(theme_color)}" />')
    favicon_ico = generated.get("favicon_ico")
    if favicon_ico:
        lines.append(f'<link rel="shortcut icon" href="{html.escape(favicon_ico)}" />')
    if icon_url:
        lines.append(
            f'<link rel="icon" type="{html.escape(_mime_type(icon_url))}" href="{html.escape(icon_url)}" />'
        )
    favicon_16 = generated.get("favicon_16")
    if favicon_16:
        lines.append(f'<link rel="icon" type="image/png" sizes="16x16" href="{html.escape(favicon_16)}" />')
    favicon_32 = generated.get("favicon_png")
    if favicon_32:
        lines.append(f'<link rel="icon" type="image/png" sizes="32x32" href="{html.escape(favicon_32)}" />')
    if apple_touch_icon_url:
        lines.append(
            f'<link rel="apple-touch-icon" sizes="180x180" href="{html.escape(apple_touch_icon_url)}" />'
        )
    if share_image_url and "://" in share_image_url:
        lines.append(f'<meta property="og:image" content="{html.escape(share_image_url)}" />')
        lines.append(f'<meta name="twitter:image" content="{html.escape(share_image_url)}" />')
        lines.append('<meta name="twitter:card" content="summary_large_image" />')
    if not lines:
        return ""
    return "\n  " + "\n  ".join(lines)


def inject_branding_head(html_text: str, head_markup: str) -> str:
    if not head_markup.strip():
        return html_text
    marker = "</head>"
    index = html_text.lower().find(marker)
    if index < 0:
        return html_text
    return f"{html_text[:index]}{head_markup}\n{html_text[index:]}"
