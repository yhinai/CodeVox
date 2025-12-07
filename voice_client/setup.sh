#!/bin/bash
# Voice Assistant Setup Script

set -e

cd "$(dirname "$0")"

echo "=========================================="
echo "Voice Assistant Setup"
echo "=========================================="
echo

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate venv
echo "Activating virtual environment..."
source venv/bin/activate

# Check if .env exists in parent directory
if [ -f "../.env" ]; then
    echo "✓ Found .env in parent directory"
    if [ ! -f ".env" ]; then
        echo "  Creating symlink to parent .env..."
        ln -s ../.env .env
    fi
else
    echo "⚠ No .env file found in parent directory"
    echo "  Please create ../.env with your XAI_API_KEY"
fi

# Check for PortAudio (required for PyAudio voice mode)
echo
echo "Checking for PortAudio (needed for voice mode)..."
if command -v pkg-config &> /dev/null; then
    if pkg-config --exists portaudio-2.0; then
        echo "✓ PortAudio is installed"
    else
        echo "⚠ PortAudio not found"
        echo
        echo "PortAudio is needed for voice mode (microphone/speaker)."
        echo "If you only need text mode, you can skip this."
        echo
        echo "To install PortAudio:"
        echo "  Ubuntu/Debian: sudo apt-get install portaudio19-dev"
        echo "  macOS: brew install portaudio"
        echo
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
else
    echo "⚠ pkg-config not found, skipping PortAudio check"
fi

# Upgrade pip
echo
echo "Upgrading pip..."
pip install --upgrade pip

# Install Python packages
echo
echo "Installing Python packages..."
pip install -r requirements.txt

echo
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo
echo "To run the voice assistant:"
echo "  python voice_assistant.py"
echo
echo "For help:"
echo "  python voice_assistant.py --help"
echo
