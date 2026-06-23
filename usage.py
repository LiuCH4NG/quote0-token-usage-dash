#!/usr/bin/env python3
"""
Fetch subscription plan usage for Kimi and GLM.

Kimi:  https://api.kimi.com/coding/v1/usages
GLM:   https://open.bigmodel.cn/api/monitor/usage/quota/limit
"""

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

@dataclass
class RateWindow:
    used_percent: float
    resets_at: Optional[datetime] = None


def format_time_until(dt: Optional[datetime]) -> str:
    if dt is None:
        return "?"
    delta = dt - datetime.now(timezone.utc)
    seconds = int(delta.total_seconds())
    if seconds <= 0:
        return "now"
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d > 0:
        return f"{d}d{h:02d}h{m:02d}m"
    if h > 0:
        return f"{h}h{m:02d}m"
    return f"{m}m"


def format_time_until_iso(iso_str: str) -> str:
    return format_time_until(datetime.fromisoformat(iso_str))


def _bar(used_pct: float, width: int = 20) -> str:
    filled = int(used_pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


# ---------------------------------------------------------------------------
# Kimi
# ---------------------------------------------------------------------------

KIMI_USAGE_URL = "https://api.kimi.com/coding/v1/usages"


def _parse_reset_time(value) -> Optional[str]:
    """Try to normalize a reset time value into an ISO-8601 string."""
    if value is None:
        return None
    if isinstance(value, str):
        # Already ISO-8601 from the API
        return value
    if isinstance(value, (int, float)):
        # Milliseconds timestamp -> ISO-8601
        ts = value / 1000 if value > 1e10 else value
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    return None


def get_kimi_usage() -> dict:
    """Fetch Kimi coding-plan usage.

    Returns a dict shaped like:
        {
            "success": True,
            "five_hour": {"utilization": float, "resets_at": str},
            "weekly_limit": {"utilization": float, "resets_at": str},
        }
    """
    api_key = os.environ.get("KIMI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("KIMI_API_KEY not set in .env")

    resp = requests.get(
        KIMI_USAGE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        timeout=15,
    )

    status = resp.status_code
    if status in (401, 403):
        raise RuntimeError(f"Kimi authentication failed (HTTP {status})")
    if status == 429:
        raise RuntimeError("Rate limited by Kimi usage endpoint. Try again in a few minutes.")
    resp.raise_for_status()

    body = resp.json()
    result: dict = {"success": True}

    # Membership level, e.g. "LEVEL_INTERMEDIATE"
    membership = body.get("user", {}).get("membership", {})
    level = membership.get("level")
    if isinstance(level, str):
        result["level"] = level.removeprefix("LEVEL_").upper()

    # 5-hour window limit (priority)
    limits = body.get("limits") or []
    if isinstance(limits, list):
        for limit_item in limits:
            detail = limit_item.get("detail") if isinstance(limit_item, dict) else None
            if not detail:
                continue
            limit = float(detail.get("limit", 1) or 1)
            used = float(detail.get("used", 0) or 0)
            resets_at = _parse_reset_time(detail.get("resetTime"))

            utilization = ((used / limit * 100.0) if limit > 0 else 0.0)
            result["five_hour"] = {
                "utilization": utilization,
                "resets_at": resets_at,
            }
            break

    # Weekly limit
    usage = body.get("usage")
    if isinstance(usage, dict):
        limit = float(usage.get("limit", 1) or 1)
        used = float(usage.get("used", 0) or 0)
        resets_at = _parse_reset_time(usage.get("resetTime"))

        utilization = ((used / limit * 100.0) if limit > 0 else 0.0)
        result["weekly_limit"] = {
            "utilization": utilization,
            "resets_at": resets_at,
        }

    return result


def print_kimi_usage(usage: dict) -> None:
    if usage.get("level"):
        print(f"Kimi plan usage ({usage['level']}):")
    else:
        print("Kimi plan usage:")
    if not usage.get("success"):
        print(f"  Error: {usage.get('error', 'unknown')}")
        return

    labels = {
        "five_hour": "5-hour  ",
        "weekly_limit": "Weekly  ",
    }
    any_data = False
    for key, label in labels.items():
        window = usage.get(key)
        if not window:
            continue
        any_data = True
        util = window["utilization"]
        remaining = 100 - util
        resets = format_time_until_iso(window["resets_at"]) if window.get("resets_at") else "?"
        print(f"  {label}  [{_bar(util)}] {util:5.1f}% used  {remaining:5.1f}% left  resets in {resets}")
    if not any_data:
        print("  No usage data returned.")


# ---------------------------------------------------------------------------
# GLM
# ---------------------------------------------------------------------------

GLM_USAGE_URL = "https://open.bigmodel.cn/api/monitor/usage/quota/limit"


@dataclass
class GLMUsage:
    primary_limit: Optional[RateWindow] = None    # 5-hour tokens
    secondary_limit: Optional[RateWindow] = None  # weekly tokens
    mcp_limit: Optional[RateWindow] = None        # MCP monthly
    level: Optional[str] = None


def _ms_to_datetime(ts) -> Optional[datetime]:
    if ts is None:
        return None
    try:
        seconds = float(ts) / 1000.0
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def get_glm_usage() -> GLMUsage:
    """Fetch GLM usage from the bigmodel.cn monitor API."""
    api_key = os.environ.get("GLM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GLM_API_KEY not set in .env")

    resp = requests.get(
        GLM_USAGE_URL,
        headers={
            "Authorization": api_key,
            "Content-Type": "application/json",
        },
        timeout=15,
    )
    resp.raise_for_status()

    payload = resp.json()
    if not payload.get("success"):
        msg = payload.get("msg") or payload.get("message") or "GLM quota query failed"
        raise RuntimeError(msg)

    data = payload.get("data") or {}
    limits = data.get("limits") or []
    if not isinstance(limits, list):
        limits = []

    token_limits = [l for l in limits if isinstance(l, dict) and l.get("type") == "TOKENS_LIMIT"]
    token_limits.sort(key=lambda l: (l.get("nextResetTime") or 0))

    mcp = next((l for l in limits if isinstance(l, dict) and l.get("type") == "TIME_LIMIT"), None)

    usage = GLMUsage(level=data.get("level"))

    if token_limits:
        first = token_limits[0]
        pct = float(first.get("percentage") or 0)
        usage.primary_limit = RateWindow(
            used_percent=pct,
            resets_at=_ms_to_datetime(first.get("nextResetTime")),
        )

    if len(token_limits) > 1:
        second = token_limits[1]
        pct = float(second.get("percentage") or 0)
        usage.secondary_limit = RateWindow(
            used_percent=pct,
            resets_at=_ms_to_datetime(second.get("nextResetTime")),
        )

    if mcp:
        total = float(mcp.get("usage") or 1000) or 1000
        used = float(mcp.get("currentValue") or 0)
        pct = (used / total * 100.0) if total > 0 else 0.0
        usage.mcp_limit = RateWindow(
            used_percent=pct,
            resets_at=_ms_to_datetime(mcp.get("nextResetTime")),
        )
        usage.mcp_limit.total = total  # type: ignore[attr-defined]
        usage.mcp_limit.used = used      # type: ignore[attr-defined]

    return usage


def print_glm_usage(usage: GLMUsage) -> None:
    print("GLM plan usage:")
    if usage.level:
        print(f"  Plan: {usage.level.upper()}")
    if usage.primary_limit:
        w = usage.primary_limit
        resets = format_time_until(w.resets_at)
        print(f"  5-hour   [{_bar(w.used_percent)}] {w.used_percent:5.1f}% used  {100-w.used_percent:5.1f}% left  resets in {resets}")
    if usage.secondary_limit:
        w = usage.secondary_limit
        resets = format_time_until(w.resets_at)
        print(f"  Weekly   [{_bar(w.used_percent)}] {w.used_percent:5.1f}% used  {100-w.used_percent:5.1f}% left  resets in {resets}")
    if usage.mcp_limit:
        w = usage.mcp_limit
        total = getattr(w, "total", 1000)
        used = getattr(w, "used", 0)
        remaining = total - used
        resets = format_time_until(w.resets_at)
        print(f"  MCP      [{_bar(w.used_percent)}] {used:.0f}/{total:.0f} used  {remaining:.0f} left  resets in {resets}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Show subscription plan usage")
    parser.add_argument("--kimi-only", action="store_true")
    parser.add_argument("--glm-only", action="store_true")
    args = parser.parse_args()

    show_kimi = not args.glm_only
    show_glm = not args.kimi_only
    errors = []

    if show_kimi:
        print()
        try:
            print_kimi_usage(get_kimi_usage())
        except Exception as e:
            errors.append(str(e))
            print(f"Kimi: error — {e}")

    if show_glm:
        print()
        try:
            print_glm_usage(get_glm_usage())
        except Exception as e:
            errors.append(str(e))
            print(f"GLM: error — {e}")

    print()
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
