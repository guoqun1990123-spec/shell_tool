@echo off
chcp 65001 >nul
title TFL Shell 配置编辑器

echo 正在启动 TFL Shell 配置编辑器...
echo.

REM 切换到项目根目录
cd /d "%~dp0"

REM 检查 streamlit 是否安装
where streamlit >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 streamlit，请先运行：pip install streamlit
    pause
    exit /b 1
)

REM 启动 streamlit 并自动打开浏览器
start "" "http://localhost:8501"
streamlit run web/app.py --server.port 8501 --server.headless true

pause
