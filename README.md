# token-usage-dash

Pushes Kimi and GLM subscription plan usage to a [dot.mindreset.tech](https://dot.mindreset.tech) e-ink display as a 296×152 image.

[中文文档](README_CN.md)

![Token usage on e-ink display](docs/preview.jpg)

## What it shows

- **Kimi** — membership level, 5-hour and weekly utilization (% used, % left, time to reset)
- **GLM** — 5-hour, weekly, and MCP monthly utilization (including used/total count)

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure

```bash
cp .env.sample .env
```

Edit `.env` with your credentials:

| Key | Description |
|-----|-------------|
| `QUOTE_API_KEY` | Bearer token from dot.mindreset.tech |
| `QUOTE_DEVICE_ID` | Device serial number |
| `KIMI_API_KEY` | API key for Kimi (`https://api.kimi.com/coding/v1/usages`) |
| `GLM_API_KEY` | API key for GLM (`https://open.bigmodel.cn/api/monitor/usage/quota/limit`) |
| `GLM_ENABLED` | Set to `false` to skip GLM fetching (default: `true`) |
| `UPDATE_INTERVAL` | Seconds between updates in loop mode (default: `1800`) |
| `QUOTE_LINK` | Optional NFC tap redirect URL for the Image API content |
| `QUOTE_BORDER` | Optional screen border color, `0` white or `1` black (default: `0`) |
| `QUOTE_DITHER_TYPE` | Optional dithering mode: `NONE`, `DIFFUSION`, or `ORDERED` (default: `NONE`) |
| `QUOTE_DITHER_KERNEL` | Optional dither kernel such as `FLOYD_STEINBERG` |
| `QUOTE_TASK_KEY` | Optional Image API task key when multiple Image API contents exist |
| `QUOTE_TASK_ALIAS` | Optional alias shown in the device task list |

### 3. Add Image API content in Content Studio

In the dot.mindreset.tech app, add an **Image API** content slot to your device. The script targets this slot. If you have multiple Image API slots, set `QUOTE_TASK_KEY` to the task key for the slot you want to update.

If the API call succeeds but the device still shows an image placeholder, the Content Studio slot may be stale or misbound. Delete the existing Image API content slot, add a fresh Image API slot to the device's active layout or playlist, then run `uv run display.py --preview` again.

## Usage

```bash
# One-shot update
uv run display.py

# Loop every 30 minutes
uv run display.py --loop

# Loop with custom interval and save preview PNG
uv run display.py --loop --interval 900 --preview

# Preview image without pushing to device
uv run render.py   # saves to /tmp/usage_preview.png

# Print usage to terminal only
uv run usage.py
uv run usage.py --kimi-only
uv run usage.py --glm-only
```

## Files

| File | Purpose |
|------|---------|
| `usage.py` | Fetches Kimi and GLM usage data |
| `render.py` | Renders the 296×152 PNG image |
| `display.py` | Orchestrates fetch → render → push to device |
