# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A small Python utility that fetches Kimi and GLM subscription usage and pushes a 296×152 black-and-white PNG to a dot.mindreset.tech e-ink display.

- `usage.py` — fetches Kimi (`api.kimi.com/coding/v1/usages`) and GLM (`open.bigmodel.cn/api/monitor/usage/quota/limit`) usage data.
- `render.py` — renders the PNG with PIL using the bundled Terminus bitmap fonts. Uses `Asia/Shanghai` timezone for the header timestamp.
- `display.py` — orchestrates fetch → render → push via the dot Image API.

There are no tests, linters, or build steps. Use `uv` for dependency management and running scripts.

## Common commands

```bash
# Install/sync dependencies
uv sync

# One-shot fetch + push to device
uv run display.py

# Loop mode (honors UPDATE_INTERVAL from .env)
uv run display.py --loop

# Save a local preview PNG without pushing
uv run display.py --preview
uv run render.py   # writes /tmp/usage_preview.png

# Print usage to terminal only
uv run usage.py
uv run usage.py --kimi-only
uv run usage.py --glm-only

# Check Python syntax
uv run python -m py_compile usage.py render.py display.py
```

## Configuration

Copy `.env.sample` to `.env` and fill in credentials. Key variables:

- `QUOTE_API_KEY` / `QUOTE_DEVICE_ID` — required for pushing to the display.
- `KIMI_API_KEY` / `GLM_API_KEY` — required for fetching provider usage.
- `GLM_ENABLED` — set to `false` to skip GLM fetching (default: `true`).
- `UPDATE_INTERVAL` — seconds between loop updates (default: `1800`).
- `QUOTE_BORDER`, `QUOTE_DITHER_TYPE`, `QUOTE_DITHER_KERNEL`, `QUOTE_TASK_KEY`, `QUOTE_TASK_ALIAS` — optional Image API parameters.

## Data shapes

- `get_kimi_usage()` returns a dict with optional keys `level`, `five_hour`, `weekly_limit`. Each window contains `utilization` (float percent) and `resets_at` (ISO-8601 string).
- `get_glm_usage()` returns a `GLMUsage` dataclass with `level` and optional `RateWindow` fields: `primary_limit` (5-hour), `secondary_limit` (weekly), `mcp_limit` (monthly). `mcp_limit` has dynamic attributes `used` and `total` for the count display.

`render_image(kimi_usage, glm_usage)` consumes these two shapes.

## Notes

- Do not commit `.env`; it contains live API keys.
- If the device shows a placeholder after a successful API call, the Image API slot in Content Studio is likely stale. Delete and re-add the slot.
- MCP row rendering intentionally omits the reset timestamp because the right-side note area is too narrow to fit both `used/total` and a long date string.
