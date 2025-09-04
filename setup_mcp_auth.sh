#!/bin/bash
# Omnispindle MCP Authentication Setup

echo "🚀 Omnispindle MCP Authentication Setup"
echo "========================================"
echo ""
echo "✨ Good news! Omnispindle now uses automatic browser authentication!"
echo ""
echo "📋 Simple setup:"
echo "1. Add Omnispindle to your MCP client configuration"
echo "2. That's it! Authentication happens automatically on first use"
echo ""
echo "🔧 MCP Configuration:"
echo "Add this to your claude_desktop_config.json:"
echo ""
echo '{'
echo '  "mcpServers": {'
echo '    "omnispindle": {'
echo '      "command": "python",'
echo '      "args": ["-m", "src.Omnispindle.stdio_server"],'
echo '      "cwd": "/path/to/Omnispindle",'
echo '      "env": {'
echo '        "OMNISPINDLE_TOOL_LOADOUT": "basic"'
echo '      }'
echo '    }'
echo '  }'
echo '}'
echo ""
echo "🌐 When you first use Omnispindle tools:"
echo "  • Your browser will open automatically"
echo "  • Log in with Google or Auth0"
echo "  • Token is saved for future use"
echo "  • All MCP tools work seamlessly!"
echo ""
echo "🛠️  Manual token setup (optional):"
echo "If you need to manually configure tokens:"

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

# Check if we're in the Omnispindle directory
if [ -f "src/Omnispindle/token_exchange.py" ]; then
    echo "  $PYTHON_CMD -m src.Omnispindle.token_exchange"
else
    echo "  cd /path/to/Omnispindle && python -m src.Omnispindle.token_exchange"
fi

echo ""
echo "✨ No configuration files to edit, no environment variables to set!"
echo "✨ Just add to your MCP config and start using Omnispindle tools!" 
