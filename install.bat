@echo off
chcp 65001 >nul
title deepseek-local-ocr
setlocal

echo.
echo   deepseek-local-ocr 一键安装
echo   让 Claude Code / Codex + DeepSeek 也能识别图片
echo.

rem 先找 Python：优先 python，回退 py
set "PY="
python --version >nul 2>&1
if not errorlevel 1 set "PY=python"
if defined PY goto pyfound
py --version >nul 2>&1
if not errorlevel 1 set "PY=py"

if not defined PY goto nopython

:pyfound
%PY% --version
echo.
echo   [1/2] 运行安装器（自动装依赖 + Skill + 规则 + 后端检查）
echo         可选参数：--skip-dep 跳过依赖  /  --no-check 跳过检查
echo.
%PY% "%~dp0install.py" %*
if errorlevel 1 (
  echo.
  echo   [失败] 安装出错了，请把上面的提示截图。
  echo.
  pause
  exit /b 1
)

echo.
echo   [2/2] 安装完成！最后一步：
echo         重启 Claude Code / Codex，再 截图 -^> Ctrl+V -^> 发消息。
echo.
pause
exit /b 0

:nopython
echo   [提示] 没有检测到 Python。
echo.
echo   本工具需要 Python 才能本地识别图片，安装很简单：
echo.
echo     方法一：Microsoft Store 搜索 Python 点安装（推荐小白）
echo     方法二：打开 https://www.python.org/downloads/ 下载安装
echo            安装时务必勾选 Add python.exe to PATH
echo.
echo   装好后重新双击本文件即可。
echo.
pause
exit /b 1
