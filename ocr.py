#!/usr/bin/env python
"""本地 OCR：用 RapidOCR 识别图片中的文字（中文为主），图片不出本机。

用法:
    python ocr.py <图片路径> [图片路径 ...]

输出格式:
    ===== <路径> ===== (耗时 X.XXs)
    [置信度] 识别到的文字
"""
import sys


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if len(sys.argv) < 2:
        print("用法: python ocr.py <图片路径> [图片路径 ...]", file=sys.stderr)
        return 1

    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()

    for path in sys.argv[1:]:
        try:
            result, elapse = engine(path)
        except Exception as exc:  # noqa: BLE001
            print(f"===== {path} ===== (识别失败)")
            print(f"错误: {exc}")
            continue

        total_elapse = sum(elapse) if isinstance(elapse, (list, tuple)) else elapse
        print(f"===== {path} ===== (耗时 {total_elapse:.2f}s)")

        if not result:
            print("未识别到文字")
            continue

        for line in result:
            # line 形如 [box, text, score]
            text = str(line[1]) if len(line) >= 2 else str(line)
            score = line[2] if len(line) >= 3 else ""
            score_str = f"[{float(score):.2f}] " if score != "" else ""
            print(f"{score_str}{text}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
