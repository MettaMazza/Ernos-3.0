#!/bin/bash
set -e

echo "═══════════════════════════════════════"
echo "  Ernos 3.0 — Docker Deployment"
echo "═══════════════════════════════════════"

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed."
    echo "   Install from: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed."
    echo "   Install from: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker and Docker Compose found."

# Setup directories
echo "📁 Setting up data directories..."
mkdir -p ./data
mkdir -p ./data/users
mkdir -p ./data/core
mkdir -p ./data/public
mkdir -p ./data/system
mkdir -p ./data/logs
mkdir -p ./models

# Setup .env
if [ ! -f ".env" ]; then
    if [ -f ".env.template" ]; then
        cp .env.template .env
        echo "📝 Created .env from template."
        echo ""
        echo "⚠️  IMPORTANT: Edit .env with your Discord bot token and other settings!"
        echo "   Run: nano .env  (or your preferred editor)"
        echo ""
        echo "   At minimum, set:"
        echo "     DISCORD_TOKEN=your_bot_token"
        echo "     ADMIN_ID=your_discord_user_id"
        echo "     NEO4J_PASSWORD=a_secure_password"
        echo ""
        read -p "Press Enter after editing .env, or Ctrl+C to abort..."
    else
        echo "❌ No .env or .env.template found. Cannot proceed."
        exit 1
    fi
fi

echo "🔨 Building Ernos image..."
docker compose build

echo "🚀 Starting Ernos stack..."
docker compose up -d

echo ""
echo "═══════════════════════════════════════"
echo "  Ernos 3.0 is starting up!"
echo "═══════════════════════════════════════"
echo ""
echo "  📋 View logs:     docker compose logs -f ernos"
echo "  🛑 Stop:          docker compose down"
echo "  🔄 Restart:       docker compose restart ernos"
echo "  🗃️  Neo4j UI:      http://localhost:7474"
echo "  🌐 Web interface: http://localhost:8080"
echo ""
echo "  Data stored in:   ./data/"
echo "  Models stored in: ./models/"
echo ""

# Pull required Ollama models
echo "📥 Pulling required Ollama models (this may take a while)..."
sleep 5  # Wait for Ollama container to start

docker exec ernos-ollama ollama pull nomic-embed-text 2>/dev/null || \
    echo "⚠️  Could not pull nomic-embed-text. Pull manually: docker exec ernos-ollama ollama pull nomic-embed-text"

echo ""
echo "✅ Setup complete! Check logs with: docker compose logs -f ernos"
