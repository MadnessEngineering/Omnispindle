# Makefile for FastMCP Todo Server

.PHONY: install run test coverage clean

# Install dependencies
install:
	uv pip install -r requirements.txt
	uv pip install -r requirements-dev.txt
	uv

# Run the FastMCP server
run:
	python3.11 -m src.Omnispindle

# deploy
deploy:
	pm2 deploy ecosystem.config.js production

# Run tests
test:
	python3.11 -m pytest tests/

# Run tests with coverage
coverage:
	python3.11 -m pytest --cov=src tests/

# Clean up __pycache__ directories
clean:
	find . -name "__pycache__" -exec rm -r {} +
