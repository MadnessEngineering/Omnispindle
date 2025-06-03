# Makefile for FastMCP Todo Server

.PHONY: install run run-dev test coverage clean status

# Install dependencies using uv
install:
	uv sync

# Install development dependencies
install-dev:
	uv sync --dev

# Run the FastMCP server using uv
run:
	uv run -m Omnispindle

# Alternative run command using the console script
run-script:
	uv run omnispindle

# Run in development mode with reload
run-dev:
	uv run -m Omnispindle

# deploy
deploy:
	pm2 deploy ecosystem.config.js production

# Run tests using uv
test:
	uv run pytest tests/

# Run tests with coverage using uv
coverage:
	uv run pytest --cov=src tests/

# Clean up __pycache__ directories
clean:
	find . -name "__pycache__" -exec rm -r {} +

# Check status of submodules and remote PM2 processes
status:
	git submodule foreach "git status"
	ssh eaws "pm2 ls"
	ssh saws "pm2 ls"
