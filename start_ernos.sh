#!/bin/bash
set -e

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
# brew install python@3.11 installs a versioned binary, usually accessible as python3.11
PYTHON_CMD="python3.11"

echo "=== Ernos 3.0 Startup Script ==="

# 1. Check for Python 3.11
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "Error: Python 3.11 is not installed or not in PATH."
    echo "Trying to find it in Homebrew paths..."
    
    if [ -f "/opt/homebrew/bin/python3.11" ]; then
        PYTHON_CMD="/opt/homebrew/bin/python3.11"
        echo "Found at $PYTHON_CMD"
    elif [ -f "/usr/local/bin/python3.11" ]; then
        PYTHON_CMD="/usr/local/bin/python3.11"
        echo "Found at $PYTHON_CMD"
    else
        echo "Could not find Python 3.11. Please run: brew install python@3.11"
        exit 1
    fi
fi
echo "✅ Python 3.11 found."

# 2. Setup/Activate Virtual Environment
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at $VENV_DIR..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
fi

echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# 3. Install/Update Dependencies
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    echo "Checking/Installing dependencies..."
    # Suppress pip upgrade warning to keep output clean, valid for user
    "$VENV_DIR/bin/pip" install --upgrade pip --quiet
    
    # Install requirements
    echo "Installing from requirements.txt (this may take a while for the first time)..."
    "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
else
    echo "Warning: requirements.txt not found in $PROJECT_DIR"
fi
echo "✅ Dependencies dependencies ready."

# 4. Check/Start Neo4j (Knowledge Graph)
if ! command -v neo4j &> /dev/null; then
    echo "⚠️  Neo4j is not installed. Installing via Homebrew..."
    brew install neo4j
fi

echo "Checking Neo4j service status..."
if ! brew services list | grep -q "neo4j.*started"; then
    echo "Starting Neo4j service..."
    brew services start neo4j
    echo "Waiting for Neo4j to warm up (this takes a few seconds)..."
    sleep 10
else
    echo "✅ Neo4j service is running."
fi

# 5. Check/Pull Ollama Models
echo "Checking Ollama models..."
if ! command -v ollama &> /dev/null; then
    echo "⚠️  Ollama is not installed. Please install it from https://ollama.com/"
else
    # Pull embedding model if missing
    if ! ollama list | grep -q "nomic-embed-text"; then
        echo "📥 Pulling embedding model 'nomic-embed-text'..."
        ollama pull nomic-embed-text
    fi
    
    # Pull reasoning model if missing (checking both likely names)
    if ! ollama list | grep -q "gemini-3-flash-preview"; then
        echo "📥 Pulling cloud model 'gemini-3-flash-preview'..."
        ollama pull gemini-3-flash-preview
    fi
    
    # Pull local model if missing
    if ! ollama list | grep -q "qwen3-vl:235b"; then
        echo "📥 Pulling local model 'qwen3-vl:235b' (This is large, please wait)..."
        ollama pull qwen3-vl:235b
    fi
    echo "✅ Ollama models ready."
fi

# 6. Launch Application
echo "🚀 Launching Ernos 3.0..."
export PYTHONPATH="$PROJECT_DIR"

# Check for .env file
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "⚠️  Warning: .env file not found. Your bot might not start if it needs secrets."
    if [ -f "$PROJECT_DIR/.env.example" ]; then
        echo "💡 Tip: Copy .env.example to .env and configure it."
    fi
fi

# Run the main bot script
python "$PROJECT_DIR/src/main.py"
