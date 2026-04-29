FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM nginx:alpine

# Copy built frontend (dist) into nginx html directory
COPY --from=frontend-builder /app/dist /usr/share/nginx/html

# Use our nginx config
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf

