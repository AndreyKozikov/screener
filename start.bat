@echo off
REM Bonds Screener Startup Script (Windows)

echo.
echo 🏦 Bonds Screener - Starting Application
echo ========================================

REM Check if Docker is installed
where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Error: Docker is not installed
    echo Please install Docker Desktop from https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

REM Check if Docker is running
docker ps >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Error: Docker is not running
    echo Please start Docker Desktop
    pause
    exit /b 1
)

REM Check if .env file exists
if not exist .env (
    echo.
    echo 📝 Creating .env file from .env.example...
    copy .env.example .env >nul
    echo ✅ .env file created. You can customize it if needed.
)

REM Stop any running containers
echo.
echo 🛑 Stopping existing containers...
docker-compose down 2>nul
if %ERRORLEVEL% NEQ 0 (
    docker compose down 2>nul
)

REM Build images
echo.
echo 🔨 Building Docker images...
docker-compose build
if %ERRORLEVEL% NEQ 0 (
    docker compose build
    if %ERRORLEVEL% NEQ 0 (
        echo ❌ Error: Failed to build images
        pause
        exit /b 1
    )
)

REM Start services
echo.
echo 🚀 Starting services...
docker-compose up -d
if %ERRORLEVEL% NEQ 0 (
    docker compose up -d
    if %ERRORLEVEL% NEQ 0 (
        echo ❌ Error: Failed to start services
        pause
        exit /b 1
    )
)

REM Wait for services
echo.
echo ⏳ Waiting for services to be ready...
timeout /t 5 /nobreak >nul

REM Show status
echo.
echo 📊 Service Status:
docker-compose ps 2>nul || docker compose ps 2>nul

echo.
echo ✅ Application started successfully!
echo.
echo 🌐 Access the application:
echo    Frontend: http://localhost:80
echo    Backend API: http://localhost:8000
echo    API Docs: http://localhost:8000/docs
echo.
echo 📝 To view logs:
echo    docker-compose logs -f (or: docker compose logs -f)
echo.
echo 🛑 To stop:
echo    docker-compose down (or: docker compose down)
echo.

pause
