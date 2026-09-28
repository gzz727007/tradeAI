# ==========================================
# A股可转债多智能体投研系统 Dockerfile
# ==========================================
FROM python:3.12-slim

# 设置时区为上海 (保证收盘时间 14:30 严格对齐)
ENV TZ=Asia/Shanghai \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1

WORKDIR /app

# 安装必要的系统运行时库与时区数据
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    gcc \
    g++ \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装 (采用国内镜像加速)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --extra-index-url https://pypi.org/simple

# 复制项目源代码
COPY . .

# 暴露 Streamlit WebUI 默认端口
EXPOSE 8501

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8501/_stcore/health || exit 1

# 默认启动命令：运行 Streamlit 可视化看板
CMD ["streamlit", "run", "ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
