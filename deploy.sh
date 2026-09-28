#!/bin/bash
# ==============================================================
# A股可转债多智能体投研交易系统 - Linux 云服务器一键部署脚本
# ==============================================================

set -e

echo "🚀 开始部署 A股可转债多智能体投研系统 (tradeAI)..."

# 1. 检查 Docker 环境
if ! command -v docker &> /dev/null; then
    echo "❌ 未检测到 Docker，请先安装 Docker。"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "❌ 未检测到 Docker Compose，请先安装 Docker Compose。"
    exit 1
fi

# 2. 检查 .env 配置文件
if [ ! -f .env ]; then
    echo "⚠️ 未发现 .env 文件，正在从 .env.example 复制模板..."
    cp .env.example .env
    echo "💡 请记得使用 nano .env 填入你的 API 密钥！"
fi

# 3. 创建数据持久化目录
mkdir -p data

# 4. 构建并启动容器
echo "📦 正在拉取依赖并构建 Docker 镜像..."
docker compose build

echo "⚡ 正在后台启动容器服务..."
docker compose up -d

echo ""
echo "=============================================================="
echo "🎉 部署完成！"
echo "🌐 Web 可视化看板访问地址: http://<你的服务器IP>:8501"
echo "📋 查看实时运行日志命令: docker compose logs -f"
echo "🛑 停止服务命令: docker compose down"
echo "=============================================================="
echo ""
echo "💡 【定时任务建议】如果你希望服务器在每个交易日下午 14:30 自动跑投研并推送报告："
echo "   运行 'crontab -e' 并添加以下一行即可："
echo "   30 14 * * 1-5 docker exec trade-ai-ui python main.py --live >> /var/log/trade_ai_daily.log 2>&1"
echo "=============================================================="
