# token-usage-dash

将 Kimi 和 GLM 的订阅套餐用量推送到 [dot.mindreset.tech](https://dot.mindreset.tech) 墨水屏，显示为一张 296×152 的黑白图片。

[English README](README.md)

![Token usage on e-ink display](docs/preview.jpg)

## 显示内容

- **Kimi** — 5 小时额度与每周额度的使用率（已用 %、剩余 %、重置时间）
- **GLM** — 5 小时额度、每周额度与 MCP 月度额度的使用率

## 安装与配置

### 1. 安装依赖

```bash
uv sync
```

### 2. 配置环境变量

```bash
cp .env.sample .env
```

编辑 `.env` 填入你的凭证：

| 配置项 | 说明 |
|--------|------|
| `QUOTE_API_KEY` | dot.mindreset.tech 的 Bearer token |
| `QUOTE_DEVICE_ID` | 设备序列号 |
| `KIMI_API_KEY` | Kimi 用量接口的 API key（`https://api.kimi.com/coding/v1/usages`） |
| `GLM_API_KEY` | GLM 监控接口的 API key（`https://open.bigmodel.cn/api/monitor/usage/quota/limit`） |
| `GLM_ENABLED` | 设为 `false` 可跳过 GLM 抓取（默认：`true`） |
| `UPDATE_INTERVAL` | `--loop` 模式下两次更新之间的秒数（默认：`1800`） |
| `QUOTE_LINK` | 可选：NFC 轻触跳转链接 |
| `QUOTE_BORDER` | 可选：屏幕边框颜色，`0` 白或 `1` 黑（默认：`0`） |
| `QUOTE_DITHER_TYPE` | 可选：抖动模式 `NONE`、`DIFFUSION`、`ORDERED`（默认：`NONE`） |
| `QUOTE_DITHER_KERNEL` | 可选：抖动核，例如 `FLOYD_STEINBERG` |
| `QUOTE_TASK_KEY` | 可选：多个 Image API 内容槽时指定任务 key |
| `QUOTE_TASK_ALIAS` | 可选：设备任务列表中显示的别名 |

### 3. 在 Content Studio 中添加 Image API 内容

在 dot.mindreset.tech App 中，为你的设备添加一个 **Image API** 内容槽，脚本会自动更新这个槽。如果有多个 Image API 槽，可设置 `QUOTE_TASK_KEY` 指定要更新的那个。

如果 API 调用成功但设备仍显示占位图，可能是 Content Studio 中的槽位已过期或绑定错误。删除旧槽位，重新添加一个 Image API 槽到设备的当前布局或播放列表，然后再次运行 `uv run display.py --preview`。

## 使用方式

```bash
# 单次更新
uv run display.py

# 每 30 分钟循环更新
uv run display.py --loop

# 自定义间隔并保存预览 PNG
uv run display.py --loop --interval 900 --preview

# 仅生成预览图，不推送设备
uv run render.py   # 保存到 /tmp/usage_preview.png

# 仅在终端打印用量
uv run usage.py
uv run usage.py --kimi-only
uv run usage.py --glm-only
```

## 文件说明

| 文件 | 作用 |
|------|------|
| `usage.py` | 抓取 Kimi 与 GLM 用量数据 |
| `render.py` | 渲染 296×152 PNG 图片 |
| `display.py` |  orchestrates 抓取 → 渲染 → 推送到设备 |
