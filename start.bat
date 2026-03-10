@echo off
TITLE AI Crypto Pilot - Titan Stack Launchpad v4.5
color 0A

echo ========================================
echo   AI CRYPTO PILOT - STARTUP SEQUENCE
echo ========================================
echo.

echo [1/5] Checking Docker status...
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

echo [2/5] Stopping any existing containers...
docker stop pilot_bot pilot_redis pilot_postgres 2>nul
docker rm pilot_bot pilot_redis pilot_postgres 2>nul
docker-compose down 2>nul
echo [OK] Cleanup complete
echo.

echo [3/5] Checking Docker image...
REM Check if image exists
docker images cryptosniperfutures-bot -q >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Using existing Docker image (cached)
    echo     To rebuild: docker-compose build --no-cache
) else (
    echo Building Docker image (first run - may take 5-10 minutes)...
    echo Please wait while we install CUDA, PyTorch, TensorFlow, and CuPy...
    docker-compose build
    if %errorlevel% neq 0 (
        color 0C
        echo.
        echo [ERROR] Docker build failed!
        echo Please check the error messages above.
        echo Common issues:
        echo   - Internet connection required for downloading packages
        echo   - Insufficient disk space
        echo   - Antivirus blocking Docker
        echo.
        pause
        exit /b 1
    )
    echo [OK] Docker image built successfully
)
echo.

echo [4/5] Starting containers...
docker-compose up -d
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Failed to start containers!
    pause
    exit /b 1
)
echo [OK] Containers started
echo.

echo [5/5] Opening monitoring tools...
timeout /t 3 >nul

REM Open logs in new window
start "AI Crypto Pilot - Logs" cmd /k "docker-compose logs -f bot"

REM Wait a moment for services to initialize
timeout /t 2 >nul

REM Open dashboard
start http://localhost/CryptoSniperFutures/index.php

color 0A
echo.
echo ========================================
echo   SYSTEM RUNNING
echo ========================================
echo.
echo Dashboard: http://localhost/CryptoSniperFutures/
echo Logs: Check the separate window
echo.
echo To stop the system: docker-compose down
echo To view logs again: docker-compose logs -f bot
echo.
echo Press any key to close this window (system will keep running)
pause >nul
