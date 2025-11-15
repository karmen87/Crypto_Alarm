#!/bin/bash

echo "======================================"
echo "  Crypto Price Alarm - Python Flask  "
echo "======================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating one..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing/updating dependencies..."
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

echo ""
echo "======================================"
echo "Starting Flask server..."
echo "Open http://localhost:5000 in your browser"
echo "Press Ctrl+C to stop the server"
echo "======================================"
echo ""

# Run the app
python app.py
