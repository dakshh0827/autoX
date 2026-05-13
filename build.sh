#!/bin/bash

# Build script for Docker image

set -e  # Exit on error

echo "🐳 Building Twitter AI Agent Docker image..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Build the image
IMAGE_NAME="twitter-ai-agent"
IMAGE_TAG="latest"

echo "📦 Building ${IMAGE_NAME}:${IMAGE_TAG}..."
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

echo "✅ Build completed successfully!"
echo ""
echo "Next steps:"
echo "1. Create .env file: cp .env.example .env"
echo "2. Edit .env and add your GROQ_API_KEY"
echo "3. Run with Docker Compose: docker-compose up"
echo ""
echo "Or run directly:"
echo "docker run -p 8000:8000 -e GROQ_API_KEY=your_key ${IMAGE_NAME}:${IMAGE_TAG}"
