#!/bin/bash

# Omnispindle Domain Setup - Redirect Only
# Sets up madnessinteractive.cc with /omnispindle redirect to GitHub
# NO MCP server endpoint - that's for later!

set -e

DOMAIN="madnessinteractive.cc"
EMAIL="danedens31@gmail.com"  # Change this to your email

echo "🚀 Setting up domain redirect (GitHub project link only)..."

# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y nginx certbot python3-certbot-nginx

# Start and enable services
sudo systemctl start nginx
sudo systemctl enable nginx

# Create nginx configuration - ONLY main domain with redirect
sudo tee /etc/nginx/sites-available/madnessinteractive << EOF
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
EOF

# Enable the site
sudo ln -sf /etc/nginx/sites-available/madnessinteractive /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx

# Get SSL certificates - ONLY for main domain
echo "📜 Obtaining SSL certificates..."
sudo certbot --nginx -d ${DOMAIN} -d www.${DOMAIN} --email ${EMAIL} --agree-tos --non-interactive

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
        .note {
            font-size: 0.9rem;
            opacity: 0.7;
            margin-top: 2rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎭 Madness Interactive</h1>
        <p>AI-Powered Development Ecosystem</p>
        
        <div class="cta">
            <h3>🔗 Current Projects</h3>
            <p><a href="/omnispindle">Omnispindle MCP Server →</a></p>
        </div>
        
        <p><em>Full website coming soon...</em></p>
        
        <div class="note">
            <p>Building something amazing with AI agents and task management!</p>
        </div>
    </div>
</body>
</html>
EOF

# Set proper permissions
sudo chown -R www-data:www-data /var/www/${DOMAIN}
sudo chmod -R 755 /var/www/${DOMAIN}

# Set up automatic SSL renewal
echo "⏰ Setting up automatic SSL renewal..."
(sudo crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && systemctl reload nginx") | sudo crontab -

echo "✅ Domain redirect setup complete!"
echo ""
echo "🌐 What's live now:"
echo "   • Main site: https://${DOMAIN} (placeholder page)"
echo "   • Project redirect: https://${DOMAIN}/omnispindle → GitHub"
echo ""
echo "🔒 SSL certificates installed and auto-renewal configured"
echo ""
echo "🎨 Next steps:"
echo "   • Build your main website in /var/www/${DOMAIN}/"
echo "   • Test: curl -I https://${DOMAIN}/omnispindle"
echo "   • MCP server endpoint will be added later when ready"
echo ""
echo "📁 Website files location: /var/www/${DOMAIN}/" 
