# 使用 Python 3.11 精简版作为后端基础镜像
FROM python:3.11-slim

# 设置容器内工作目录
WORKDIR /app

# 禁止 Python 生成 .pyc 缓存文件
ENV PYTHONDONTWRITEBYTECODE=1

# 让 Python 日志实时输出，不进入缓冲区
ENV PYTHONUNBUFFERED=1

# 复制后端依赖清单
COPY requirements.txt ./

# 安装后端 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制 FastAPI 应用代码
COPY app ./app

# 复制数据库初始化脚本
COPY scripts ./scripts

# 声明后端容器监听 8000 端口
EXPOSE 8000

# 启动前初始化测试账号，然后启动 FastAPI 服务
CMD ["sh", "-c", "python scripts/init_user.py && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
