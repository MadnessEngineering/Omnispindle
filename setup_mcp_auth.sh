#!/bin/bash
# Omnispindle MCP Authentication Setup - One-liner installer

# The actual one-liner that users can run:
# curl -sSL https://raw.githubusercontent.com/yourusername/Omnispindle/main/setup_mcp_auth.sh | bash

# Or for local execution:
# python -m src.Omnispindle.token_exchange

echo "🚀 Omnispindle MCP Authentication Setup"
echo "========================================"

# Check if Python is installed
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "❌ Python is not installed. Please install Python 3.8+ first."
    exit 1
fi

# Determine Python command
PYTHON_CMD="python"
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
fi

# Check if we're in the Omnispindle directory or need to clone it
if [ -f "src/Omnispindle/token_exchange.py" ]; then
    echo "✅ Found local Omnispindle installation"
    $PYTHON_CMD -m src.Omnispindle.token_exchange
else
    echo "📦 Setting up Omnispindle..."
    
    # Create temporary directory
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"
    
    # Clone the repository (shallow clone for speed)
    echo "📥 Downloading Omnispindle..."
    git clone --depth 1 https://github.com/yourusername/Omnispindle.git
    
    cd Omnispindle
    
    # Install minimal requirements
    echo "📦 Installing dependencies..."
    $PYTHON_CMD -m pip install httpx --quiet
    
    # Run the token exchange
    $PYTHON_CMD -m src.Omnispindle.token_exchange
    
    # Clean up
    cd /
    rm -rf "$TEMP_DIR"
fi

echo ""
echo "✨ Setup complete! Restart Claude Desktop to start using Omnispindle." 
