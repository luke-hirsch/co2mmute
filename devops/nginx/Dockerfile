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
# Certs are NOT baked into the image — they are bind-mounted at run time
# (see devops/docker-compose.yaml). A private key must never live in the repo.
COPY devops/nginx/robots.txt /usr/share/nginx/html/robots.txt
COPY --from=frontend-build /app/dist ./app

RUN mkdir -p /var/www/backend-static
