#!/bin/bash

# Build script for Hugging Face Spaces

set -e  # Exit on error

echo "🤗 Building for Hugging Face Spaces..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Build the Hugging Face optimized image
IMAGE_NAME="twitter-ai-agent-hf"
IMAGE_TAG="latest"

echo "📦 Building Hugging Face optimized image..."
docker build -f Dockerfile.huggingface -t ${IMAGE_NAME}:${IMAGE_TAG} .

echo "✅ Hugging Face image built successfully!"
echo ""
echo "Next steps for Hugging Face Spaces deployment:"
echo "1. Go to https://huggingface.co/spaces and create a new Space"
echo "2. Choose 'Docker' as the runtime"
echo "3. Push your code to the Space's git repository"
echo ""
echo "Commands:"
echo "git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/SPACE_NAME"
echo "git push hf main"
