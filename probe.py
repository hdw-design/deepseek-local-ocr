#!/usr/bin/env python
"""探测 DeepSeek /anthropic 端点对 image 内容块是报错还是忽略。

从 ~/.claude/settings.json 读取 ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN / 模型名，
只发一个 1x1 透明 PNG，不会打印密钥。适用于 Claude Code 直连 DeepSeek 等纯文本后端的场景。
"""
import json
import os
import sys
import urllib.error
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SETTINGS = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
if not os.path.exists(SETTINGS):
    print("ERROR: 找不到 ~/.claude/settings.json，请先配置好 Claude Code 后端再运行。")
    sys.exit(1)

cfg = json.load(open(SETTINGS, encoding="utf-8"))
env = cfg.get("env") or {}
base = (env.get("ANTHROPIC_BASE_URL") or "").rstrip("/")
token = env.get("ANTHROPIC_AUTH_TOKEN") or ""
# 注意：deepseek-chat / deepseek-reasoner 已于 2026-07-24 弃用，
# 回退统一用 deepseek-v4-flash（非思考、更快更便宜）
model = (
    env.get("ANTHROPIC_DEFAULT_FABLE_MODEL")
    or env.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
    or env.get("ANTHROPIC_DEFAULT_CLAUDE_MODEL")
    or env.get("ANTHROPIC_MODEL")
    or "deepseek-v4-flash"
)
if not base or not token:
    print("ERROR: ~/.claude/settings.json 的 env 里缺少 ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN。")
    sys.exit(1)

# 1x1 透明 PNG
png_b64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

body = {
    "model": model,
    "max_tokens": 16,
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": png_b64}},
                {"type": "text", "text": "ping"},
            ],
        }
    ],
}

# 走用户配置里的本地代理，与 Claude Code 实际网络路径一致
proxy = env.get("HTTPS_PROXY") or env.get("HTTP_PROXY")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({"https": proxy})) if proxy else None

req = urllib.request.Request(
    base + "/v1/messages",
    data=json.dumps(body).encode(),
    headers={
        "Content-Type": "application/json",
        "x-api-key": token,
        "Authorization": f"Bearer {token}",
        "anthropic-version": "2023-06-01",
    },
    method="POST",
)

try:
    resp = opener.open(req, timeout=40) if opener else urllib.request.urlopen(req, timeout=40)
    print("STATUS:", resp.status)
    print(resp.read(2000).decode(errors="replace"))
except urllib.error.HTTPError as e:
    print("HTTP ERROR:", e.code)
    print(e.read(2000).decode(errors="replace"))
except Exception as e:  # noqa: BLE001
    print("ERROR:", type(e).__name__, e)