FROM node:22-alpine AS builder

WORKDIR /app
ARG VITE_CESIUM_ION_TOKEN=
ENV VITE_CESIUM_ION_TOKEN=${VITE_CESIUM_ION_TOKEN}
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY public ./public
COPY src ./src
RUN npm run build

FROM nginx:1.27-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
