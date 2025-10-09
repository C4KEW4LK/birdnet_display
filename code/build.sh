#!/bin/bash

# Build script for BirdNET Display (Go version)

set -e

echo "Building BirdNET Display..."
echo ""

# Build main application
echo "Building main server..."
go build -o birdnet_display main.go
if [ $? -eq 0 ]; then
    echo "✓ Main server built successfully"
else
    echo "✗ Failed to build main server"
    exit 1
fi

echo ""

# Build cache builder
echo "Building cache builder..."
go build -o cache_builder ./cmd/cache_builder/main.go
if [ $? -eq 0 ]; then
    echo "✓ Cache builder built successfully"
else
    echo "✗ Failed to build cache builder"
    exit 1
fi

echo ""
echo "Build complete!"
echo ""
echo "Binaries created:"
echo "  - birdnet_display (main server)"
echo "  - cache_builder (cache building tool)"
echo ""
echo "To run:"
echo "  ./birdnet_display -h       # Show server options"
echo "  ./cache_builder -h         # Show cache builder options"
