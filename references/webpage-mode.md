# Webpage Mode

Use this mode when the user wants a local HTML newspaper page instead of a text-only summary.

## Default style

- style id: `people-daily-v1`

This mode reuses the local analysis bundle and a reviewed `summary.json`, then renders a static local page through the multi-page newspaper pipeline used by the local `group-daily-newspaper` workflow. It does not publish anything.

## Workflow

1. Run `scripts/prepare_wechat_digest.py`
2. Read the generated `analysis/*.briefing.md`
3. Draft `summary.json` using `references/summary-schema.md`
4. Render:

```bash
python3 scripts/render_web_digest.py \
  --summary /abs/path/to/summary.json \
  --analysis /abs/path/to/analysis.json
```

## Output files

The renderer writes:

- `<group_dir>/<since>_<until>.web.md`
- `<group_dir>/summary.json`
- `<group_dir>/newspaper/<since>_<until>/story.json`
- `<group_dir>/newspaper/<since>_<until>/layout-plan.json`
- `<group_dir>/site/index.html`
- `<group_dir>/dist/index.html`
- `<group_dir>/history.json`
- `<group_dir>/history-digests.jsonl`

Optional group branding:

- Put a square image at `<group_dir>/branding/site-icon.png` (or `.jpg` / `.jpeg` / `.webp`) to generate favicon assets for the rendered site.
- Add `<group_dir>/branding/site-branding.json` to set `theme_color`, `icon_public_url`, `apple_touch_icon_public_url`, or `og_image_public_url` when you want explicit meta tags instead of only the generated local assets.

## Content rules

- Keep the page grounded in real messages and data.
- Favor 4-6 strong threads instead of trying to cover everything.
- Use real names and real quotes.
- Use `period_in_one_line` for the core takeaway of the selected range.
- Default to newspaper-style editorial wording: headline, deck, lead, sidebars, timeline, quote rail.
- Quiet days should still read like an intentional "静版" or "无新稿" edition, not a product empty state.
- Do not add deployment URLs, domain advice, or server instructions.
