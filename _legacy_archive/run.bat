@echo off
title Servers Manager

:: 切换到当前批处理文件所在的目录
cd /d "%~dp0"

:: 虚拟环境
call .venv\Scripts\activate

echo Starting all servers from directory: %cd%
echo.

rem 启动 Node.js 服务器
start "Node Server SERVER" node node_server/server.js

rem 启动 Python 服务器
start "Python Server" python python_server/app.py
start "Setup" python python_server/setup.py

echo.
echo All server startup commands have been issued.
echo Each server is running in its own window.
echo.

pause