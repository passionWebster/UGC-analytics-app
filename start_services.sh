#!/bin/bash

# Bilibili Analytics Platform - 启动脚本
# 一键启动前后端服务

echo "🚀 正在启动 Bilibili Analytics Platform..."
echo "======================================"

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 Python 3"
    exit 1
fi

# 检查 Node.js 环境
if ! command -v node &> /dev/null; then
    echo "❌ 错误: 未找到 Node.js"
    exit 1
fi

# 启动后端服务 (FastAPI)
echo ""
echo "📦 启动后端服务..."
cd "$(dirname "$0")/backend"

# 检查并安装 Python 依赖
if [ ! -d "../venv" ]; then
    echo "  正在创建 Python 虚拟环境..."
    python3 -m venv ../venv
fi

source ../venv/bin/activate
pip install -q -r requirements.txt

# 后台启动 FastAPI
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "  ✅ 后端服务已启动 (PID: $BACKEND_PID)"
echo "  📖 API 文档: http://localhost:8000/api/docs"

# 启动前端服务 (Vue 3 + Vite)
echo ""
echo "🎨 启动前端服务..."
cd ../frontend

# 检查并安装 Node 依赖
if [ ! -d "node_modules" ]; then
    echo "  正在安装前端依赖..."
    npm install
fi

# 后台启动 Vite
nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  ✅ 前端服务已启动 (PID: $FRONTEND_PID)"
echo "  🌐 前端地址: http://localhost:5173"

# 保存 PID
cd ..
mkdir -p logs
echo $BACKEND_PID > logs/backend.pid
echo $FRONTEND_PID > logs/frontend.pid

echo ""
echo "======================================"
echo "🎉 所有服务启动成功！"
echo ""
echo "📊 后端 API: http://localhost:8000"
echo "🌐 前端应用: http://localhost:5173"
echo ""
echo "查看日志:"
echo "  后端: tail -f logs/backend.log"
echo "  前端: tail -f logs/frontend.log"
echo ""
echo "停止服务: ./stop_services.sh"
echo "======================================"
