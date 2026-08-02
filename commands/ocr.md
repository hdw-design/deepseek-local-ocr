---
description: 用本地 RapidOCR 识别图片中的文字（中英文），图片不出本机
---

用户需要识别图片里的文字。用本地 OCR 脚本处理，不要尝试把图片发给模型（后端是纯文本模型，不支持 image 内容块）。

## 流程

1. 确定图片来源：
   - 用户给了图片路径 → 直接用。
   - 用户说「截图」「刚粘贴的」或没给路径 → 说明是剪贴板截图，先执行下面的「剪贴板截图保存」。
   - 用户拖进来的图片没有对应路径 → 引导用户把图片保存成文件并给出路径，或直接截图后再次调用 /ocr。

2. 运行脚本（多个图片可以一起传）：

   ```powershell
   python "$HOME\.claude\skills\deepseek-local-ocr\scripts\ocr.py" "<路径1>" ["<路径2>" ...]
   ```

3. 整理输出回复：
   - 去掉 `=====` 分隔行和 `[置信度]` 前缀，保留识别出的文字本身。
   - 如果识别内容是代码、报错信息或命令，用代码块呈现，方便复制。
   - 如果识别质量差（置信度低、断行乱），如实说明，不要编造没识别出的内容。

## 剪贴板截图保存（无路径时）

用 PowerShell 把剪贴板图片存成临时 PNG，再对它跑 ocr.py：

```powershell
Add-Type -AssemblyName System.Windows.Forms
$img = [System.Windows.Forms.Clipboard]::GetImage()
if ($img) {
    $img.Save("$HOME\.claude\skills\deepseek-local-ocr\scripts\clipboard.png")
    "saved"
} else {
    "no image in clipboard"
}
```

处理完后删除临时文件 `$HOME\.claude\skills\deepseek-local-ocr\scripts\clipboard.png`。
