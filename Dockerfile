# ============================
# 后端多阶段构建
# ============================
FROM python:3.13-slim AS backend

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY backend/ .

# 不复制 .env、sessions、logs 等敏感/运行时目录
# 这些通过 volume 挂载

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
