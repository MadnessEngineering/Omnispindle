# Makefile for FastMCP Todo Server

.PHONY: install run test coverage clean status deploy

# Install dependencies
install:
	uv pip install -r requirements.txt
	uv pip install -r requirements-dev.txt
	# uv pip install -r requirements-prod.txt

# Run the FastMCP server
run:
	python3.11 -m src.Omnispindle
	COMMIT_HASH=$(git rev-parse --short HEAD)
	mosquitto_pub -h localhost -p 4140 -t "status/$(DeName)/commit" -m "{\"commit_hash\": \"$(COMMIT_HASH)\"}"

# deploy
deploy:
	rsync -avI /Users/d.edens/lab/madness_interactive/projects/python/Omnispindle/Todomill_projectorium/Html ubuntu@($AWSIP:/home/ubuntu/.node-red/projects/saws-flow/src/
	rsync -avI /Users/d.edens/lab/madness_interactive/projects/python/Omnispindle/Todomill_projectorium/Javascript ubuntu@$AWSIP:~/.node-red/projects/saws-flow/src/

# Run tests
test:
	python3.11 -m pytest tests/

# Run tests with coverage
coverage:
	python3.11 -m pytest --cov=src tests/

# Clean up __pycache__ directories
clean:
	find . -name "__pycache__" -exec rm -r {} +

# Check status of submodules and remote PM2 processes
status:
	git submodule foreach "git status"
	ssh eaws "pm2 ls"
	ssh saws "pm2 ls"
