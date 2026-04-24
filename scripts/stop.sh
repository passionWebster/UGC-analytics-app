#!/bin/bash

# UGC Streaming Analytics Platform - 停止脚本

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "🛑 正在停止服务..."

if [ -f "$ROOT_DIR/logs/backend.pid" ]; then
    BACKEND_PID=$(cat "$ROOT_DIR/logs/backend.pid")
    if kill -0 $BACKEND_PID 2>/dev/null; then
        kill $BACKEND_PID
        echo "  ✅ 后端服务已停止"
    fi
    rm "$ROOT_DIR/logs/backend.pid"
fi

if [ -f "$ROOT_DIR/logs/frontend.pid" ]; then
    FRONTEND_PID=$(cat "$ROOT_DIR/logs/frontend.pid")
    if kill -0 $FRONTEND_PID 2>/dev/null; then
        kill $FRONTEND_PID
        echo "  ✅ 前端服务已停止"
    fi
    rm "$ROOT_DIR/logs/frontend.pid"
fi

echo "🎉 所有服务已停止"
