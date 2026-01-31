#!/bin/bash

# Bilibili Analytics Platform - 停止脚本

echo "🛑 正在停止服务..."

if [ -f "logs/backend.pid" ]; then
    BACKEND_PID=$(cat logs/backend.pid)
    if kill -0 $BACKEND_PID 2>/dev/null; then
        kill $BACKEND_PID
        echo "  ✅ 后端服务已停止"
    fi
    rm logs/backend.pid
fi

if [ -f "logs/frontend.pid" ]; then
    FRONTEND_PID=$(cat logs/frontend.pid)
    if kill -0 $FRONTEND_PID 2>/dev/null; then
        kill $FRONTEND_PID
        echo "  ✅ 前端服务已停止"
    fi
    rm logs/frontend.pid
fi

echo "🎉 所有服务已停止"
