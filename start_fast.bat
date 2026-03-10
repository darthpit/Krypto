@echo off
TITLE AI Crypto Pilot - Fast Start (Uses Cache)
color 0A

echo ========================================
echo   AI CRYPTO PILOT - FAST START
echo ========================================
echo.

echo [1/4] Checking Docker status...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Docker is not running!
    echo Please start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)
echo [OK] Docker is running
echo.

echo [2/4] Checking Docker image...
docker images cryptosniperfutures-bot -q >nul 2>&1
if %errorlevel% neq 0 (
    color 0E
    echo [WARNING] Docker image not found!
    echo Please run start.bat first to build the image.
    echo.
    pause
    exit /b 1
)
echo [OK] Image exists, starting containers...
docker-compose up -d
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Failed to start containers!
    echo.
    echo If image doesn't exist, run: start.bat
    echo.
    pause
    exit /b 1
)
echo [OK] Containers started
echo.

echo [3/4] Waiting for services to initialize...
timeout /t 5 >nul
echo [OK] Services ready
echo.

echo [4/4] Opening monitoring tools...
REM Open logs in new window
start "AI Crypto Pilot - Logs" cmd /k "docker-compose logs -f bot"

REM Wait a moment for log window to open
timeout /t 1 >nul

REM Open dashboard
start http://localhost/CryptoSniperFutures/index.php

color 0A
echo.
echo ========================================
echo   SYSTEM RUNNING (FAST MODE)
echo ========================================
echo.
echo Dashboard: http://localhost/CryptoSniperFutures/
echo Logs: Check the separate window
echo.
echo To stop the system: docker-compose down
echo To view logs again: docker-compose logs -f bot
echo To rebuild image: start.bat or docker-compose build
echo.
echo Press any key to close this window (system will keep running)
pause >nul
