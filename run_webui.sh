#!/bin/bash
# Lazer Gimbal (HSS) - WebUI Launch Script for macOS / Linux

echo "======================================================="
echo "🎯 STARTING LAZER GIMBAL HSS WEB COMMAND CENTER..."
echo "======================================================="

# Activate virtual environment if present
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Build WebUI frontend if dist does not exist
if [ ! -d "webui/dist" ]; then
    echo "📦 Building WebUI React + Three.js application..."
    cd webui && npm install && npm run build && cd ..
fi

echo "🚀 Launching FastAPI Backend & Web Server on http://localhost:8000"
python3 web_server.py --port 8000 --host 0.0.0.0
