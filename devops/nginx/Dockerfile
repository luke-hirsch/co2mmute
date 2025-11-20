FROM node:20-alpine AS frontend-build
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend .

ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

FROM nginx:1.27-alpine
WORKDIR /usr/share/nginx/html

COPY devops/nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY devops/nginx/certs /etc/nginx/certs
COPY --from=frontend-build /app/dist .

RUN mkdir -p /var/www/backend-static
