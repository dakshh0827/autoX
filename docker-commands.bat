@echo off
REM Quick Docker commands helper script for Windows

setlocal enabledelayedexpansion

if "%1%"=="" goto help
if "%1%"=="help" goto help
if "%1%"=="build" goto build
if "%1%"=="build-hf" goto build-hf
if "%1%"=="run" goto run
if "%1%"=="compose-up" goto compose-up
if "%1%"=="compose-down" goto compose-down
if "%1%"=="compose-logs" goto compose-logs
if "%1%"=="health" goto health
if "%1%"=="test-api" goto test-api
if "%1%"=="ps" goto ps
if "%1%"=="cleanup" goto cleanup

echo Unknown command: %1%
goto help

:build
echo 🐳 Building Docker image...
docker build -t twitter-ai-agent:latest .
goto end

:build-hf
echo 🤗 Building Hugging Face optimized image...
docker build -f Dockerfile.huggingface -t twitter-ai-agent-hf:latest .
goto end

:run
if "%2%"=="" (
    echo ❌ GROQ_API_KEY required
    echo Usage: docker-commands.bat run YOUR_API_KEY
    exit /b 1
)
echo 🚀 Running container...
docker run -p 8000:8000 ^
    -e GROQ_API_KEY=%2% ^
    -e BROWSER_HEADLESS=True ^
    twitter-ai-agent:latest
goto end

:compose-up
echo 🐳 Starting with Docker Compose...
docker-compose up -d
echo ✅ Service running at http://localhost:8000
goto end

:compose-down
echo 🛑 Stopping Docker Compose services...
docker-compose down
goto end

:compose-logs
echo 📋 Showing logs...
docker-compose logs -f twitter-agent
goto end

:health
echo 🏥 Checking health...
curl http://localhost:8000/health
goto end

:test-api
echo 🧪 Testing API endpoint...
curl -X POST http://localhost:8000/api/v1/run ^
    -H "Content-Type: application/json" ^
    -d "{\"topic\": \"artificial intelligence\"}"
goto end

:ps
echo 📦 Running containers:
docker ps | findstr twitter
goto end

:cleanup
echo 🧹 Cleaning up Docker resources...
docker-compose down
docker rmi twitter-ai-agent:latest twitter-ai-agent-hf:latest
echo ✅ Cleanup complete
goto end

:help
echo 🐳 Twitter AI Agent - Docker Helper (Windows)
echo.
echo Usage: docker-commands.bat [command]
echo.
echo Commands:
echo   build              Build the Docker image
echo   build-hf           Build Hugging Face optimized image
echo   run ^<API_KEY^>      Run container (needs GROQ_API_KEY)
echo   compose-up         Start services with Docker Compose
echo   compose-down       Stop services
echo   compose-logs       View service logs
echo   health             Check API health
echo   test-api           Test the API endpoint
echo   ps                 List running containers
echo   cleanup            Remove containers and images
echo   help               Show this help message
echo.
echo Examples:
echo   docker-commands.bat build
echo   docker-commands.bat compose-up
echo   docker-commands.bat run sk-xxxxx
goto end

:end
endlocal
