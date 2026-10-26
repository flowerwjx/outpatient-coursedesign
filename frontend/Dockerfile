# 第一阶段使用 Node 20 Alpine 镜像构建前端
FROM node:20-alpine AS build

# 设置前端构建工作目录
WORKDIR /app

# 复制前端依赖清单和锁文件
COPY package.json package-lock.json ./

# 安装前端依赖
RUN npm install

# 复制前端源代码和配置文件
COPY . .

# 执行前端生产构建，输出 dist 目录
RUN npm run build

# 第二阶段使用 Nginx Alpine 镜像托管静态文件
FROM nginx:alpine

# 从构建阶段复制 dist 到 Nginx 静态目录
COPY --from=build /app/dist /usr/share/nginx/html

# 复制自定义 Nginx 配置，启用 /api 反向代理
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 声明前端容器监听 80 端口
EXPOSE 80

# 使用前台模式启动 Nginx
CMD ["nginx", "-g", "daemon off;"]
