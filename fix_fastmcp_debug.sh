#!/bin/bash

# Fix FastMCP ServerErrorMiddleware debug warnings
# Run this script after pip updates to reapply the debug=False hack
# Compatible with Ubuntu/Linux and macOS

echo "🔧 Fixing FastMCP debug mode to suppress ServerErrorMiddleware warnings..."

# Try to find Python executable (try python3 first, then python)
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ No Python executable found. Install Python first."
    exit 1
fi

echo "📍 Using Python: $PYTHON_CMD"

# Find FastMCP installation path
FASTMCP_PATH=$($PYTHON_CMD -c "import fastmcp; print(fastmcp.__file__)" 2>/dev/null | sed 's/__init__.py$//')

if [ -z "$FASTMCP_PATH" ]; then
    echo "❌ FastMCP not found. Make sure it's installed."
    echo "   Try: pip install fastmcp"
    exit 1
fi

echo "📂 FastMCP found at: $FASTMCP_PATH"

SERVER_FILE="${FASTMCP_PATH}server/server.py"

if [ ! -f "$SERVER_FILE" ]; then
    echo "❌ FastMCP server.py not found at $SERVER_FILE"
    exit 1
fi

# Create backup if it doesn't exist
if [ ! -f "${SERVER_FILE}.backup" ]; then
    echo "📋 Creating backup of original server.py..."
    cp "$SERVER_FILE" "${SERVER_FILE}.backup"
fi

# Check if hack is already applied
if grep -q "debug=False" "$SERVER_FILE"; then
    echo "✅ FastMCP debug hack already applied!"
    exit 0
fi

# Apply the hack (Linux-compatible sed syntax)
echo "🔨 Applying debug=False hack..."
# Detect OS for sed syntax
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' 's/debug=self\.settings\.debug/debug=False/g' "$SERVER_FILE"
else
    # Linux/Ubuntu
    sed -i 's/debug=self\.settings\.debug/debug=False/g' "$SERVER_FILE"
fi

# Verify the change
if grep -q "debug=False" "$SERVER_FILE"; then
    echo "✅ FastMCP debug hack applied successfully!"
    echo "🚀 ServerErrorMiddleware warnings should now be suppressed."
    echo ""
    echo "📍 Modified file: $SERVER_FILE"
    echo ""
    echo "To restore original behavior, run:"
    echo "cp '${SERVER_FILE}.backup' '$SERVER_FILE'"
else
    echo "❌ Failed to apply hack. Check the file manually."
    echo "📍 Target file: $SERVER_FILE"
    exit 1
fi
