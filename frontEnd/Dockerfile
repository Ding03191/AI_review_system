FROM nginx:alpine

# 删除默认的 Nginx 配置
RUN rm -rf /etc/nginx/conf.d/*

# 复制自定义 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制前端文件到 Nginx 服务目录
COPY public/ /usr/share/nginx/html/
COPY src/ /usr/share/nginx/html/src/

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
