#!/bin/bash
# Build script for Video Censor standalone app
# Usage: ./build.sh

set -e

echo "🎬 Building Video Censor standalone app..."

# Activate virtual environment if not active
if [ -z "$VIRTUAL_ENV" ]; then
    source venv/bin/activate
fi

# Ensure PyInstaller is installed
pip install pyinstaller --quiet

# Clean previous builds
rm -rf build dist

# Build the app
echo "📦 Running PyInstaller..."
pyinstaller VideoCensor.spec --noconfirm

# Copy config template into the app
cp config.yaml.example "dist/VideoCensor.app/Contents/MacOS/"

# Create a zip for distribution
echo "🗜️  Creating distributable zip..."
cd dist
zip -r -q VideoCensor-macOS.zip VideoCensor.app
cd ..

echo ""
echo "✅ Build complete!"
echo ""
echo "📍 App location: dist/VideoCensor.app"
echo "📦 Distributable: dist/VideoCensor-macOS.zip"
echo ""
echo "To install:"
echo "  1. Upload VideoCensor-macOS.zip to GitHub Releases"
echo "  2. Users download, unzip, and drag to Applications"
echo ""
