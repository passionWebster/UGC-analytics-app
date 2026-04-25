#!/bin/bash

# Bilibili Analytics Platform - 生产模式启动脚本
# 前端使用 production build + vite preview，避免直接运行 dev server

echo "🚀 正在以生产模式启动 Bilibili Analytics Platform..."
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

# 项目根目录
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_PORT="${PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-4173}"

# 启动后端服务 (FastAPI)
echo ""
echo "📦 启动后端服务..."
cd "$ROOT_DIR/backend"

# 检查并安装 Python 依赖
if [ ! -d "$ROOT_DIR/venv" ]; then
    echo "  正在创建 Python 虚拟环境..."
    python3 -m venv "$ROOT_DIR/venv"
fi

source "$ROOT_DIR/venv/bin/activate"
pip install -q -r requirements.txt

# 后台启动 FastAPI
mkdir -p "$ROOT_DIR/logs"
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" > "$ROOT_DIR/logs/backend.log" 2>&1 &
BACKEND_PID=$!
echo "  ✅ 后端服务已启动 (PID: $BACKEND_PID)"
echo "  📖 API 文档: http://localhost:${BACKEND_PORT}/api/docs"

# 启动前端服务 (Vue 3 + Vite Preview)
echo ""
echo "🎨 构建并启动前端服务..."
cd "$ROOT_DIR/frontend"

# 安装前端依赖
if [ ! -d "node_modules" ]; then
    echo "  正在安装前端依赖..."
    npm install
fi

echo "  正在执行前端生产构建..."
npm run build

# 后台启动 Vite Preview（生产构建产物）
VITE_BACKEND_PORT="$BACKEND_PORT" nohup npm run preview -- --host 0.0.0.0 --port "$FRONTEND_PORT" > "$ROOT_DIR/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "  ✅ 前端服务已启动 (PID: $FRONTEND_PID)"
echo "  🌐 前端地址: http://localhost:${FRONTEND_PORT}"

# 保存 PID
echo $BACKEND_PID > "$ROOT_DIR/logs/backend.pid"
echo $FRONTEND_PID > "$ROOT_DIR/logs/frontend.pid"

echo ""
echo "======================================"
echo "🎉 所有服务启动成功（生产模式）！"
echo ""
echo "📊 后端 API: http://localhost:${BACKEND_PORT}"
echo "🌐 前端应用: http://localhost:${FRONTEND_PORT}"
echo ""
echo "查看日志:"
echo "  后端: tail -f logs/backend.log"
echo "  前端: tail -f logs/frontend.log"
echo ""
echo "停止服务: ./scripts/stop.sh"
echo "======================================"
