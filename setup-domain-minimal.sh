#!/bin/bash

# Minimal Omnispindle Domain Setup
# Only sets up mcp.madnessinteractive.cc for the MCP server

set -e

MCP_SUBDOMAIN="mcp.madnessinteractive.cc"
EMAIL="danedens31@gmail.com"
CONTAINER_PORT="8000"

echo "🚀 Setting up minimal MCP server domain..."

# Install essentials
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx docker.io docker-compose

# Start services
sudo systemctl start nginx docker
sudo systemctl enable nginx docker

# Simple nginx config - ONLY for MCP server
sudo tee /etc/nginx/sites-available/mcp-omnispindle << EOF
server {
    listen 80;
    server_name ${MCP_SUBDOMAIN};
    
    location / {
        proxy_pass http://127.0.0.1:${CONTAINER_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    location /health {
        proxy_pass http://127.0.0.1:${CONTAINER_PORT}/health;
    }
    
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/mcp-omnispindle /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Get SSL certificate (only for MCP subdomain)
sudo certbot --nginx -d ${MCP_SUBDOMAIN} --email ${EMAIL} --agree-tos --non-interactive

echo "✅ Minimal setup complete!"
echo "🌐 MCP Server: https://${MCP_SUBDOMAIN}"
echo "🔧 Start your server: docker run -p 127.0.0.1:8000:8000 danedens31/omnispindle:latest" 
