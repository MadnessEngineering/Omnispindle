# Makefile for FastMCP Todo Server

# set default device name to Omnispindle
DeNa ?= omnispindle

.PHONY: install run test coverage clean status deploy deploy-dry-run deploy-force

# Install dependencies
install:
	uv pip install -r requirements.txt
	uv pip install -r requirements-dev.txt
	# uv pip install -r requirements-prod.txt

# Run the FastMCP server (HTTP - recommended for remote)
run:
	fastmcp run src/Omnispindle/http_server.py
	COMMIT_HASH=$(git rev-parse --short HEAD)
	mosquitto_pub -h localhost -p 4140 -t "status/$(DeNa)/commit" -m "{\"commit_hash\": \"$(COMMIT_HASH)\"}"

# Run the old SSE server (legacy)
run-sse:
	python3.11 -m src.Omnispindle
	COMMIT_HASH=$(git rev-parse --short HEAD)
	mosquitto_pub -h localhost -p 4140 -t "status/$(DeNa)/commit" -m "{\"commit_hash\": \"$(COMMIT_HASH)\"}"

# Run stdio server locally  
run-stdio:
	python3.11 -m src.Omnispindle.stdio_server

# deploy — pull latest on eaws and restart
deploy:
	ssh eaws "cd /home/ubuntu/Omnispindle && git pull origin main && pm2 restart Omnispindle-HTTP"

# deploy-dry-run — show what would change
deploy-dry-run:
	ssh eaws "cd /home/ubuntu/Omnispindle && git fetch origin main && git log HEAD..origin/main --oneline"

# deploy-force — hard reset to origin/main then restart
deploy-force:
	ssh eaws "cd /home/ubuntu/Omnispindle && git fetch origin main && git reset --hard origin/main && pm2 restart Omnispindle-HTTP"

# Run tests
test:
	python -m pytest tests/

# Run tests with coverage
coverage:
	python -m pytest --cov=src tests/

# Clean up __pycache__ directories
clean:
	find . -name "__pycache__" -exec rm -r {} +

# Check status of submodules and remote PM2 processes
status:
	git submodule foreach "git status"
	ssh eaws "pm2 ls"
	ssh saws "pm2 ls"

sync:
	git submodule foreach "git pull || echo No changes"
	ssh eaws "cd ~/Omnispindle && git pull"
	ssh eaws "pm2 restart Omnispindle"
	sleep 2 && ssh eaws "pm2 logs Omnispindle --lines 10 && exit"
