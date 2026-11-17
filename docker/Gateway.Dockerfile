FROM node:24.14.0-bookworm-slim AS controls
WORKDIR /build
COPY apps/frontend/package.json apps/frontend/package-lock.json ./
RUN npm ci --ignore-scripts
COPY apps/frontend/ ./
RUN npm run build

FROM nginx:1.28.0-alpine
COPY --from=controls /build/dist /usr/share/nginx/html/controls
COPY modules/ai-gods-eye-view/public/brand-icons /usr/share/nginx/html/brand-icons
COPY docker/gateway.conf.template /etc/nginx/templates/default.conf.template
COPY docker/viewer-headers.conf /etc/nginx/viewer-headers.conf
EXPOSE 443
