#!/bin/bash

# Build and publish Omnispindle to PyPI
# Phase 3: PyPI Package Preparation - Build and Publish Script

set -e

echo "🐍 Building Omnispindle Python package for PyPI..."

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build/ dist/ *.egg-info/

# Install build dependencies if not available
echo "📦 Ensuring build dependencies are available..."
pip install --upgrade build twine

# Build the package
echo "🔨 Building package..."
python -m build

# Verify the build
echo "✅ Verifying built package..."
python -m twine check dist/*

# Show what was built
echo "📋 Built packages:"
ls -la dist/

echo "🎯 Package ready for PyPI!"
echo ""
echo "To publish to PyPI:"
echo "  Test PyPI: python -m twine upload --repository testpypi dist/*"
echo "  Production: python -m twine upload dist/*"
echo ""
echo "To install from PyPI after publishing:"
echo "  pip install omnispindle"
echo ""
echo "CLI commands will be available:"
echo "  - omnispindle (web server)"
echo "  - omnispindle-server (alias for web server)"  
echo "  - omnispindle-stdio (MCP stdio server)"