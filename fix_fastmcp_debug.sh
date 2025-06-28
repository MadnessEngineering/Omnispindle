#!/bin/bash

# Fix FastMCP ServerErrorMiddleware debug warnings
# Run this script after pip updates to reapply the debug=False hack

echo "🔧 Fixing FastMCP debug mode to suppress ServerErrorMiddleware warnings..."

# Find FastMCP installation path
FASTMCP_PATH=$(python -c "import fastmcp; print(fastmcp.__file__)" 2>/dev/null | sed 's/__init__.py$//')

if [ -z "$FASTMCP_PATH" ]; then
    echo "❌ FastMCP not found. Make sure it's installed."
    exit 1
fi

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

# Apply the hack
echo "🔨 Applying debug=False hack..."
sed -i '' 's/debug=self\.settings\.debug/debug=False/g' "$SERVER_FILE"

# Verify the change
if grep -q "debug=False" "$SERVER_FILE"; then
    echo "✅ FastMCP debug hack applied successfully!"
    echo "🚀 ServerErrorMiddleware warnings should now be suppressed."
    echo ""
    echo "To restore original behavior, run:"
    echo "cp '${SERVER_FILE}.backup' '$SERVER_FILE'"
else
    echo "❌ Failed to apply hack. Check the file manually."
    exit 1
fi 
