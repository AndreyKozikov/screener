#!/bin/bash

# Bonds Screener Startup Script (Unix/Linux/macOS)

set -e

echo "🏦 Bonds Screener - Starting Application"
echo "========================================"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed"
    echo "Please install Docker from https://www.docker.com/get-started"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Error: Docker Compose is not installed"
    echo "Please install Docker Compose"
    exit 1
fi

# Check if .env file exists, if not copy from example
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "✅ .env file created. You can customize it if needed."
fi

# Stop any running containers
echo ""
echo "🛑 Stopping existing containers..."
docker-compose down 2>/dev/null || docker compose down 2>/dev/null || true

# Build and start services
echo ""
echo "🔨 Building Docker images..."
if command -v docker-compose &> /dev/null; then
    docker-compose build
else
    docker compose build
fi

echo ""
echo "🚀 Starting services..."
if command -v docker-compose &> /dev/null; then
    docker-compose up -d
else
    docker compose up -d
fi

# Wait for services to be healthy
echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check service status
echo ""
echo "📊 Service Status:"
if command -v docker-compose &> /dev/null; then
    docker-compose ps
else
    docker compose ps
fi

echo ""
echo "✅ Application started successfully!"
echo ""
echo "🌐 Access the application:"
echo "   Frontend: http://localhost:80"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "📝 To view logs:"
echo "   docker-compose logs -f (or: docker compose logs -f)"
echo ""
echo "🛑 To stop:"
echo "   docker-compose down (or: docker compose down)"
echo ""
