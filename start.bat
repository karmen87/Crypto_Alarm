@echo off
echo ======================================
echo   Crypto Price Alarm (Binance)
echo ======================================
echo.

if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Installing/updating dependencies...
pip install -q -e .

echo.
echo Open http://localhost:5000 in your browser. Press Ctrl+C to stop.
echo.

python -m crypto_alarm

pause
