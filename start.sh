#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -d venv ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing/updating dependencies..."
pip install -q -e .

echo
echo "Open http://localhost:5000 in your browser. Press Ctrl+C to stop."
echo

python -m crypto_alarm
