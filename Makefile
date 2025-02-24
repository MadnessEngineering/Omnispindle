# Makefile for FastMCP Todo Server

.PHONY: install run test coverage clean

# Install dependencies
install:
	uv pip install -r requirements.txt
	uv pip install -r requirements-dev.txt

# Run the FastMCP server
run:
	python -m src.fastmcp_todo_server

# Run tests
test:
	pytest tests/

# Run tests with coverage
coverage:
	pytest --cov=src tests/

# Clean up __pycache__ directories
clean:
	find . -name "__pycache__" -exec rm -r {} +
