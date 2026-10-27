# ============================================================
# 第一阶段：构建 Vue3 前端
# 构建上下文必须是项目根目录，才能同时访问 frontend/ 和 backend/
# ============================================================
FROM node:20-alpine AS frontend-build

# 设置前端构建工作目录
WORKDIR /frontend

# 复制前端依赖清单和锁文件
COPY frontend/package.json frontend/package-lock.json ./

# 安装前端依赖
RUN npm install

# 复制前端源代码和配置文件
COPY frontend/ ./

# 执行前端生产构建，生成 dist
RUN npm run build


# ============================================================
# 第二阶段：构建 Python 后端运行时镜像
# ============================================================
FROM python:3.11-slim

# 设置后端工作目录
WORKDIR /app

# 禁止 Python 生成 .pyc 缓存文件
ENV PYTHONDONTWRITEBYTECODE=1

# 让 Python 日志实时输出
ENV PYTHONUNBUFFERED=1

# Render 免费层没有持久磁盘，默认 SQLite 文件放在应用目录
ENV DATABASE_URL=sqlite:////app/his.db

# 复制后端依赖清单
COPY backend/requirements.txt ./

# 安装后端 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制 FastAPI 应用代码
COPY backend/app ./app

# 复制数据库初始化脚本
COPY backend/scripts ./scripts

# 复制第一阶段构建好的前端静态文件
COPY --from=frontend-build /frontend/dist ./static

# 声明容器默认监听 8000 端口
EXPOSE 8000

# 启动前初始化账号，然后使用 Render 提供的 PORT 启动服务
CMD ["sh", "-c", "python scripts/init_user.py && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
