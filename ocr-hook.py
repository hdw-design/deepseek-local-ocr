#!/usr/bin/env python
"""UserPromptSubmit 自动 OCR 钩子。

用户粘贴图片提交后，把图片从 session transcript 中找出来（base64），
本地 OCR 成文字，输出到 stdout。对 UserPromptSubmit 钩子，stdout 会作为上下文注入给模型。

为什么轮询：Claude Code 的 transcript 是异步写入的，钩子触发时当前消息可能还没刷进文件。
本钩子在找不到图片时，会短时间轮询等待当前用户消息写入，再提取图片。

图片查找策略（按顺序）：
  1. 解析 session transcript（transcript_path），找最近一条带图片的用户消息
  2. 轮询等待当前消息写入（异步滞后补偿）
  3. 扫描缓存目录中最近写入的图片文件（兼容不同版本的目录名）
用 state 文件按 (路径, mtime) 去重，避免同一张图被反复 OCR。
"""
import base64
import json
import os
import subprocess
import sys
import time

OCR_DIR = os.path.dirname(os.path.abspath(__file__))
CLAUDE_DIR = os.path.join(os.path.expanduser("~"), ".claude")
DEBUG_LOG = os.path.join(OCR_DIR, "hook-debug.log")
STATE_FILE = os.path.join(OCR_DIR, ".hook-state.json")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
MAX_CTX = 10000
POLL_SECONDS = 4.0
POLL_INTERVAL = 0.15


def log(msg: str) -> None:
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S") + " " + msg + "\n")
    except Exception:
        pass


def load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state: dict) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def count_lines(path: str) -> int:
    if not path or not os.path.exists(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def tail_has_user(path: str, after: int) -> bool:
    """transcript 在 `after` 行之后是否出现了新的 user 消息（即当前消息已写入）。"""
    if not path or not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return False
    for line in lines[after:]:
        try:
            obj = json.loads(line.lstrip("﻿"))
        except Exception:
            continue
        msg = obj.get("message") if isinstance(obj, dict) else None
        if isinstance(msg, dict) and msg.get("role") == "user":
            return True
    return False


def recent_images(folders, within=180) -> list:
    """返回缓存目录里最近写入的图片文件 [(path, age_seconds)]，新的在前。"""
    now = time.time()
    found = []
    for folder in folders:
        if not folder or not os.path.isdir(folder):
            continue
        for root, _dirs, files in os.walk(folder):
            for fn in files:
                if not fn.lower().endswith(IMAGE_EXT):
                    continue
                p = os.path.join(root, fn)
                try:
                    age = now - os.path.getmtime(p)
                except OSError:
                    continue
                if 0 <= age <= within:
                    found.append((p, age))
    return sorted(found, key=lambda x: x[1])


def transcript_images(tpath: str) -> list:
    """从 transcript 尾部找最近一条带图片的用户消息，解码 base64 存为临时 png。"""
    if not tpath or not os.path.exists(tpath):
        return []
    try:
        with open(tpath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        log(f"transcript read error: {e}")
        return []
    results = []
    scanned = 0
    for line in reversed(lines):
        scanned += 1
        if scanned > 80:  # 只翻最近 80 行，避免命中的是很久以前的图
            break
        try:
            obj = json.loads(line.lstrip("﻿"))
        except Exception:
            continue
        msg = obj.get("message") if isinstance(obj, dict) else None
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list):
            continue
        images = [c for c in content if isinstance(c, dict) and c.get("type") == "image"]
        if not images:
            continue
        if (msg or {}).get("role") != "user":
            break  # 遇到非 user 的带图消息就停，避免取到旧图
        for c in images:
            src = c.get("source", {}) or {}
            if src.get("type") == "base64" and src.get("data"):
                tmp = os.path.join(OCR_DIR, "hook_img.png")
                try:
                    with open(tmp, "wb") as f:
                        f.write(base64.b64decode(src["data"]))
                    results.append(tmp)
                except Exception as e:
                    log(f"decode image error: {e}")
        return results
    return results


def discover(tpath: str, folders: list, state: dict) -> list:
    """收集候选图片并去掉已处理过的，返回新图片路径列表。"""
    candidates = transcript_images(tpath)
    for p, _age in recent_images(folders):
        if p not in candidates:
            candidates.append(p)
    new_ones = []
    for p in candidates:
        try:
            m = os.path.getmtime(p)
        except OSError:
            continue
        if state.get(p) != m:
            new_ones.append(p)
    return new_ones


def ocr(path: str) -> str:
    try:
        r = subprocess.run(
            [sys.executable, os.path.join(OCR_DIR, "ocr.py"), path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=25,
        )
        return r.stdout or ""
    except Exception as e:
        log(f"ocr failed {path}: {e}")
        return ""


def main() -> int:
    try:
        raw = (sys.stdin.read() or "").lstrip("﻿").strip()
        data = json.loads(raw) if raw else {}
    except Exception:
        return 0
    session_id = data.get("session_id", "")
    transcript_path = data.get("transcript_path", "")
    log(
        "HOOK session=%s transcript=%s"
        % (session_id, os.path.basename(transcript_path) if transcript_path else "-")
    )

    folders = [
        os.path.join(CLAUDE_DIR, "image-cache", session_id) if session_id else None,
        os.path.join(CLAUDE_DIR, "image-cache"),
        os.path.join(CLAUDE_DIR, "paste-cache"),
        os.path.join(CLAUDE_DIR, "downloads"),
    ]

    state = load_state()
    new_ones = discover(transcript_path, folders, state)

    # 异步写入补偿：当前消息可能还没刷进 transcript，短时轮询等待
    if not new_ones and transcript_path:
        base = count_lines(transcript_path)
        deadline = time.time() + POLL_SECONDS
        while time.time() < deadline:
            if tail_has_user(transcript_path, base):
                break  # 当前用户消息已写入，做一次最终提取
            time.sleep(POLL_INTERVAL)
        new_ones = discover(transcript_path, folders, state)
        if new_ones:
            log(f"found image after {POLL_SECONDS - (deadline - time.time()):.1f}s poll")

    if not new_ones:
        log("no new image (candidates=%d)" % len(new_ones))
        for fld in folders:
            if fld and os.path.isdir(fld):
                try:
                    n = len(os.listdir(fld))
                except Exception:
                    n = -1
                log("  dir %s: %d items" % (fld, n))
        return 0

    text_lines = []
    for p in new_ones:
        out = ocr(p)
        keep = []
        for ln in out.splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("===") or ln.startswith("未识别"):
                continue
            if ln.startswith("[") and "]" in ln:
                ln = ln.split("]", 1)[1].strip()
            keep.append(ln)
        if keep:
            text_lines.append("[%s]" % os.path.basename(p))
            text_lines.extend(keep)
        try:
            state[p] = os.path.getmtime(p)
        except OSError:
            pass
    save_state(state)

    if not text_lines:
        log("ocr produced no text")
        return 0

    ctx = (
        "【本地自动OCR】你在本条消息中粘贴了图片，已用本地 OCR 识别，内容如下，"
        "请直接依据这些文字理解图片，无需再提示用户：\n" + "\n".join(text_lines)
    )[:MAX_CTX]
    log("inject %d chars" % len(ctx))
    sys.stdout.write(ctx)
    return 0


if __name__ == "__main__":
    sys.exit(main())
