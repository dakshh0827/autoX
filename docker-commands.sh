#!/bin/bash

# Quick Docker commands helper script

CMD=${1:-help}

case $CMD in
    "build")
        echo "🐳 Building Docker image..."
        docker build -t twitter-ai-agent:latest .
        ;;
    
    "build-hf")
        echo "🤗 Building Hugging Face optimized image..."
        docker build -f Dockerfile.huggingface -t twitter-ai-agent-hf:latest .
        ;;
    
    "run")
        if [ -z "$2" ]; then
            echo "❌ GROQ_API_KEY required"
            echo "Usage: ./docker-commands.sh run YOUR_API_KEY"
            exit 1
        fi
        echo "🚀 Running container..."
        docker run -p 8000:8000 \
            -e GROQ_API_KEY=$2 \
            -e BROWSER_HEADLESS=True \
            twitter-ai-agent:latest
        ;;
    
    "compose-up")
        echo "🐳 Starting with Docker Compose..."
        docker-compose up -d
        echo "✅ Service running at http://localhost:8000"
        ;;
    
    "compose-down")
        echo "🛑 Stopping Docker Compose services..."
        docker-compose down
        ;;
    
    "compose-logs")
        echo "📋 Showing logs..."
        docker-compose logs -f twitter-agent
        ;;
    
    "health")
        echo "🏥 Checking health..."
        curl http://localhost:8000/health
        ;;
    
    "test-api")
        echo "🧪 Testing API endpoint..."
        curl -X POST http://localhost:8000/api/v1/run \
            -H "Content-Type: application/json" \
            -d '{"topic": "artificial intelligence"}'
        ;;
    
    "ps")
        echo "📦 Running containers:"
        docker ps | grep twitter
        ;;
    
    "cleanup")
        echo "🧹 Cleaning up Docker resources..."
        docker-compose down
        docker rmi twitter-ai-agent:latest twitter-ai-agent-hf:latest 2>/dev/null || true
        echo "✅ Cleanup complete"
        ;;
    
    "help")
        echo "🐳 Twitter AI Agent - Docker Helper"
        echo ""
        echo "Usage: ./docker-commands.sh [command]"
        echo ""
        echo "Commands:"
        echo "  build              Build the Docker image"
        echo "  build-hf           Build Hugging Face optimized image"
        echo "  run <API_KEY>      Run container (needs GROQ_API_KEY)"
        echo "  compose-up         Start services with Docker Compose"
        echo "  compose-down       Stop services"
        echo "  compose-logs       View service logs"
        echo "  health             Check API health"
        echo "  test-api           Test the API endpoint"
        echo "  ps                 List running containers"
        echo "  cleanup            Remove containers and images"
        echo "  help               Show this help message"
        echo ""
        echo "Examples:"
        echo "  ./docker-commands.sh build"
        echo "  ./docker-commands.sh compose-up"
        echo "  ./docker-commands.sh run sk-xxxxx"
        ;;
    
    *)
        echo "❌ Unknown command: $CMD"
        echo "Run './docker-commands.sh help' for available commands"
        exit 1
        ;;
esac
