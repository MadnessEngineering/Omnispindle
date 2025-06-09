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
# Main domain - ready for your website
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};
    
    # Omnispindle project redirect
    location /omnispindle {
        return 301 https://github.com/DanEdens/Omnispindle;
    }
    
    # Future website root - for now, show a placeholder
    location / {
        root /var/www/${DOMAIN};
        index index.html index.htm;
        try_files \$uri \$uri/ =404;
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

# Create website directory and placeholder page
sudo mkdir -p /var/www/${DOMAIN}
sudo tee /var/www/${DOMAIN}/index.html << EOF
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Madness Interactive - Coming Soon</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            text-align: center;
        }
        .container {
            max-width: 600px;
            padding: 2rem;
        }
        h1 {
            font-size: 3rem;
            margin-bottom: 1rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        p {
            font-size: 1.2rem;
            margin-bottom: 2rem;
            opacity: 0.9;
        }
        .cta {
            background: rgba(255,255,255,0.2);
            padding: 1rem 2rem;
            border-radius: 10px;
            backdrop-filter: blur(10px);
            margin: 2rem 0;
        }
        a {
            color: #ffd700;
            text-decoration: none;
            font-weight: bold;
        }
        a:hover {
            text-shadow: 0 0 10px #ffd700;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎭 Madness Interactive</h1>
        <p>AI-Powered Development Ecosystem</p>
        
        <div class="cta">
            <h3>🔗 Quick Links</h3>
            <p><a href="/omnispindle">Omnispindle MCP Server →</a></p>
            <p><a href="https://mcp.madnessinteractive.cc">MCP API Endpoint →</a></p>
        </div>
        
        <p><em>Full website coming soon...</em></p>
    </div>
</body>
</html>
EOF

# Set proper permissions
sudo chown -R www-data:www-data /var/www/${DOMAIN}
sudo chmod -R 755 /var/www/${DOMAIN}

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
echo "🌐 Your domain structure:"
echo "   • Main site: https://${DOMAIN} (placeholder page ready for your website)"
echo "   • Omnispindle project: https://${DOMAIN}/omnispindle (redirects to GitHub)"
echo "   • MCP Server: https://${MCP_SUBDOMAIN}"
echo "   • Health check: https://${MCP_SUBDOMAIN}/health"
echo ""
echo "📋 Next steps:"
echo "   1. Wait for DNS propagation (up to 24 hours)"
echo "   2. Run: docker-compose -f docker-compose.prod.yml up -d"
echo "   3. Test: curl https://${MCP_SUBDOMAIN}/health"
echo "   4. Enable service: sudo systemctl enable omnispindle"
echo ""
echo "🎨 Website Development:"
echo "   • Edit files in /var/www/${DOMAIN}/"
echo "   • The placeholder page is live and ready to customize"
echo "   • SSL certificates are configured for all domains"
echo ""
echo "🔧 To update the server:"
echo "   docker-compose -f docker-compose.prod.yml pull && docker-compose -f docker-compose.prod.yml up -d" 
