@echo off
echo ======================================
echo   Crypto Price Alarm - Python Flask
echo ======================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo Virtual environment not found. Creating one...
    python -m venv venv
    echo [OK] Virtual environment created
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing/updating dependencies...
pip install -q -r requirements.txt
echo [OK] Dependencies installed

echo.
echo ======================================
echo Starting Flask server...
echo Open http://localhost:5000 in your browser
echo Press Ctrl+C to stop the server
echo ======================================
echo.

REM Run the app
python app.py

pause
