# ── Stage 1: 构建前端 ──
FROM node:22-alpine AS frontend-builder

WORKDIR /app/frontend

# 利用 Docker 缓存层：先拷贝依赖文件
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --prefer-offline

# 拷贝源码并构建
COPY frontend/ ./
RUN npm run build

# ── Stage 2: 后端 + 前端静态文件 ──
FROM python:3.11-slim

WORKDIR /app

# 系统依赖（PyMuPDF 的轻量运行时，不装 magic-pdf 的 PyTorch 全家桶）
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 拷贝并安装 Python 依赖
# 注意: magic-pdf (MinerU) 需要 PyTorch ~2GB，若镜像过大可注释掉该行
COPY requirements.txt ./
RUN pip install --no-cache-dir \
    fastapi>=0.115.0 \
    "uvicorn[standard]>=0.30.0" \
    openai>=1.0.0 \
    "langgraph>=0.2.50,<0.3.0" \
    "langgraph-checkpoint-sqlite>=2.0.0,<2.1.0" \
    "langchain-core>=0.3.0,<0.4.0" \
    pymed>=0.8.0 \
    PyMuPDF>=1.23.0 \
    sqlalchemy>=2.0.0 \
    python-dotenv>=1.0.0 \
    httpx>=0.27.0 \
    pytest>=8.0

# magic-pdf 太重了(需要 PyTorch ~2GB)，MinerU PDF 解析在这里跳过；
# 若确实需要，把上面 pip install 换成: pip install --no-cache-dir -r requirements.txt
# 并在系统依赖里补上: libgl1-mesa-glx libglib2.0-0

# 拷贝后端代码
COPY backend/ ./backend/

# 拷贝前端构建产物（Stage 1）
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist/

# 数据目录（运行时通过 volume 挂载）
RUN mkdir -p /app/data

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:7860/api/health || exit 1

CMD ["python", "-m", "backend.main"]
