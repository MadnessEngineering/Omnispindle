ker.sh${NC}"
echo ""
echo -e "The Todo Dashboard will be available at: ${YELLOW}http://localhost:3001${NC}"
echo ""

# Ask if user wants to start the environment now
read -p "Would you like to start the Docker environment now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting Docker environment..."
    ./start-docker.sh
fi
