# 改造该项目

把Claude， codex用量的查询， 换成Kimi和GLM

kimi用量查询参考
```rust
async fn query_kimi(api_key: &str) -> SubscriptionQuota {
    let client = crate::proxy::http_client::get();

    let resp = client
        .get("https://api.kimi.com/coding/v1/usages")
        .header("Authorization", format!("Bearer {api_key}"))
        .header("Accept", "application/json")
        .timeout(std::time::Duration::from_secs(15))
        .send()
        .await;

    let resp = match resp {
        Ok(r) => r,
        Err(e) => return make_error(format!("Network error: {e}")),
    };

    let status = resp.status();
    if status == reqwest::StatusCode::UNAUTHORIZED || status == reqwest::StatusCode::FORBIDDEN {
        return SubscriptionQuota {
            tool: "coding_plan".to_string(),
            credential_status: CredentialStatus::Expired,
            credential_message: Some("Invalid API key".to_string()),
            success: false,
            tiers: vec![],
            extra_usage: None,
            error: Some(format!("Authentication failed (HTTP {status})")),
            queried_at: Some(now_millis()),
        };
    }

    if !status.is_success() {
        let body = resp.text().await.unwrap_or_default();
        return make_error(format!("API error (HTTP {status}): {body}"));
    }

    let body: serde_json::Value = match resp.json().await {
        Ok(v) => v,
        Err(e) => return make_error(format!("Failed to parse response: {e}")),
    };

    let mut tiers = Vec::new();

    // 5 小时窗口限额（优先显示）
    if let Some(limits) = body.get("limits").and_then(|v| v.as_array()) {
        for limit_item in limits {
            if let Some(detail) = limit_item.get("detail") {
                let limit = detail.get("limit").and_then(parse_f64).unwrap_or(1.0);
                let remaining = detail.get("remaining").and_then(parse_f64).unwrap_or(0.0);
                let resets_at = detail.get("resetTime").and_then(extract_reset_time);

                let used = (limit - remaining).max(0.0);
                let utilization = if limit > 0.0 {
                    (used / limit) * 100.0
                } else {
                    0.0
                };
                tiers.push(QuotaTier {
                    name: "five_hour".to_string(),
                    utilization,
                    resets_at,
                    used_value_usd: None,
                    max_value_usd: None,
                });
            }
        }
    }

    // 总体用量（周限额）
    if let Some(usage) = body.get("usage") {
        let limit = usage.get("limit").and_then(parse_f64).unwrap_or(1.0);
        let remaining = usage.get("remaining").and_then(parse_f64).unwrap_or(0.0);
        let resets_at = usage.get("resetTime").and_then(extract_reset_time);

        let used = (limit - remaining).max(0.0);
        let utilization = if limit > 0.0 {
            (used / limit) * 100.0
        } else {
            0.0
        };
        tiers.push(QuotaTier {
            name: "weekly_limit".to_string(),
            utilization,
            resets_at,
            used_value_usd: None,
            max_value_usd: None,
        });
    }

    SubscriptionQuota {
        tool: "coding_plan".to_string(),
        credential_status: CredentialStatus::Valid,
        credential_message: None,
        success: true,
        tiers,
        extra_usage: None,
        error: None,
        queried_at: Some(now_millis()),
    }
}
```

GLM的查询参考 
({
  request: {
    url: "https://open.bigmodel.cn/api/monitor/usage/quota/limit",
    method: "GET",
    headers: {
      Authorization: "{{apiKey}}",
      "Content-Type": "application/json",
    },
  },
  extractor: (response) => {
    if (response.success && response.data) {
      const limits = response.data.limits;
      const level = response.data.level || "unknown";

      const tokenLimits = limits.filter((l) => l.type === "TOKENS_LIMIT");
      tokenLimits.sort((a, b) => a.nextResetTime - b.nextResetTime);

      const mcp = limits.find((l) => l.type === "TIME_LIMIT");

      // 辅助函数：将毫秒时间戳转换为 "下次重置 xxx 分钟后" 的格式
      const formatResetTime = (timestamp) => {
        if (!timestamp) return "";
        const diffMs = timestamp - Date.now();
        if (diffMs <= 0) return "下次重置 0 分钟后";
        // 如果时间非常久（比如按月），把分钟转换成天或小时会更易读
        const diffMin = Math.ceil(diffMs / (1000 * 60));
        const diffHours = Math.floor(diffMin / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffDays > 0) {
          const remainHours = diffHours % 24;
          return `下次重置 ${diffDays} 天 ${remainHours} 小时后`;
        } else if (diffHours > 0) {
          const remainMins = diffMin % 60;
          return `下次重置 ${diffHours} 小时 ${remainMins} 分钟后`;
        } else {
          return `下次重置 ${diffMin} 分钟后`;
        }
      };

      const result = [
        {
          planName: `${level.toUpperCase()} · 5小时额度`,
          remaining: 100 - (tokenLimits[0]?.percentage || 0),
          used: tokenLimits[0]?.percentage || 0,
          unit: "%",
          extra: formatResetTime(tokenLimits[0]?.nextResetTime),
        },
      ];

      // 新套餐有每周限额（两个 TOKENS_LIMIT），老套餐只有一个
      if (tokenLimits.length > 1) {
        result.push({
          planName: `${level.toUpperCase()} · 每周额度`,
          remaining: 100 - (tokenLimits[1].percentage || 0),
          used: tokenLimits[1].percentage || 0,
          unit: "%",
          extra: formatResetTime(tokenLimits[1].nextResetTime),
        });
      }

      if (mcp) {
        result.push({
          planName: "MCP每月",
          remaining: mcp.remaining || 0,
          used: mcp.currentValue || 0,
          total: mcp.usage || 1000,
          unit: "次",
          extra: formatResetTime(mcp.nextResetTime),
        });
      }

      return result;
    }
    return [
      {
        isValid: false,
        invalidMessage: response.msg || "查询余额查询失败",
      },
    ];
  },
});