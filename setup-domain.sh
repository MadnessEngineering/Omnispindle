#!/bin/bash

# Omnispindle Domain Setup Script
# Sets up madnessinteractive.cc with SSL and reverse proxy

set -e

DOMAIN="madnessinteractive.cc"
MCP_SUBDOMAIN="mcp.madnessinteractive.cc"
EMAIL="danedens31@gmail.com"  # Change this to your email
CONTAINER_PORT="8000"

echo "🚀 Setting up Omnispindle MCP Server domain configuration..."

# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y nginx certbot python3-certbot-nginx docker.io docker-compose

# Start and enable services
sudo systemctl start nginx
sudo systemctl enable nginx
sudo systemctl start docker
sudo systemctl enable docker

# Add user to docker group
sudo usermod -aG docker $USER

# Create nginx configuration for MCP server
sudo tee /etc/nginx/sites-available/omnispindle << EOF
# Main domain
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};
    
    location / {
        return 301 https://github.com/DanEdens/Omnispindle;
    }
    
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
}

# MCP Server subdomain
server {
    listen 80;
    server_name ${MCP_SUBDOMAIN};
    
    location / {
        proxy_pass http://127.0.0.1:${CONTAINER_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    location /health {
        proxy_pass http://127.0.0.1:${CONTAINER_PORT}/health;
        proxy_set_header Host \$host;
    }
    
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
}
EOF

# Enable the site
sudo ln -sf /etc/nginx/sites-available/omnispindle /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx

# Get SSL certificates
echo "📜 Obtaining SSL certificates..."
sudo certbot --nginx -d ${DOMAIN} -d www.${DOMAIN} -d ${MCP_SUBDOMAIN} --email ${EMAIL} --agree-tos --non-interactive

# Create docker-compose override for production
cat > docker-compose.prod.yml << EOF
version: '3.8'

services:
  omnispindle:
    image: danedens31/omnispindle:latest
    container_name: omnispindle-prod
    restart: unless-stopped
    ports:
      - "127.0.0.1:${CONTAINER_PORT}:8000"
    environment:
      - HOST=0.0.0.0
      - PORT=8000
      - MONGODB_URI=mongodb://mongo:27017
      - MONGODB_DB=swarmonomicon
      - MQTT_HOST=mosquitto
      - MQTT_PORT=1883
      - DOMAIN=${MCP_SUBDOMAIN}
    depends_on:
      - mongo
      - mosquitto
    networks:
      - omnispindle-network

  mongo:
    image: mongo:7
    container_name: omnispindle-mongo
    restart: unless-stopped
    ports:
      - "127.0.0.1:27017:27017"
    volumes:
      - mongodb_data:/data/db
    networks:
      - omnispindle-network

  mosquitto:
    image: eclipse-mosquitto:2
    container_name: omnispindle-mosquitto
    restart: unless-stopped
    ports:
      - "127.0.0.1:1883:1883"
      - "127.0.0.1:9001:9001"
    volumes:
      - ./mosquitto.conf:/mosquitto/config/mosquitto.conf
      - mosquitto_data:/mosquitto/data
      - mosquitto_log:/mosquitto/log
    networks:
      - omnispindle-network

volumes:
  mongodb_data:
  mosquitto_data:
  mosquitto_log:

networks:
  omnispindle-network:
    driver: bridge
EOF

# Create mosquitto configuration
mkdir -p mosquitto
cat > mosquitto/mosquitto.conf << EOF
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log
log_dest stdout

listener 1883
allow_anonymous true

listener 9001
protocol websockets
allow_anonymous true
EOF

# Set up automatic SSL renewal
echo "⏰ Setting up automatic SSL renewal..."
(sudo crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && systemctl reload nginx") | sudo crontab -

# Create systemd service for automatic startup
sudo tee /etc/systemd/system/omnispindle.service << EOF
[Unit]
Description=Omnispindle MCP Server
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/\$USER/omnispindle
ExecStart=/usr/local/bin/docker-compose -f docker-compose.prod.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.prod.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Domain setup complete!"
echo ""
echo "🌐 Your Omnispindle MCP Server will be available at:"
echo "   • Main site: https://${DOMAIN}"
echo "   • MCP Server: https://${MCP_SUBDOMAIN}"
echo "   • Health check: https://${MCP_SUBDOMAIN}/health"
echo ""
echo "📋 Next steps:"
echo "   1. Wait for DNS propagation (up to 24 hours)"
echo "   2. Run: docker-compose -f docker-compose.prod.yml up -d"
echo "   3. Test: curl https://${MCP_SUBDOMAIN}/health"
echo "   4. Enable service: sudo systemctl enable omnispindle"
echo ""
echo "🔧 To update the server:"
echo "   docker-compose -f docker-compose.prod.yml pull && docker-compose -f docker-compose.prod.yml up -d" 
