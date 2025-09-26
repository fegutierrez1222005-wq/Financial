FROM nginx:alpine

# Copy built frontend (dist) into nginx html directory
COPY ../frontend/dist /usr/share/nginx/html

# Use our nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

