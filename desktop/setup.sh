#!/bin/bash
# Typeoff setup — creates venv, installs platform-appropriate dependencies
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "─── Typeoff Setup ───"

# Install system dependencies
if [[ "$(uname)" == "Darwin" ]]; then
    if ! command -v ffmpeg &>/dev/null; then
        echo "Installing ffmpeg..."
        brew install ffmpeg 2>/dev/null || echo "⚠  Install ffmpeg manually: brew install ffmpeg"
    fi
    if ! pkg-config --exists portaudio 2>/dev/null; then
        echo "Installing portaudio..."
        brew install portaudio 2>/dev/null || echo "⚠  Install portaudio manually: brew install portaudio"
    fi
elif command -v apt &>/dev/null; then
    echo "Installing system dependencies..."
    sudo apt install -y libportaudio2 python3-venv python3-dev 2>/dev/null || {
        echo "⚠  Could not install system deps. Run manually:"
        echo "   sudo apt install libportaudio2 python3-venv python3-dev"
    }
fi

# Find best Python
for PY in python3.13 python3.12 python3.11 python3; do
    if command -v "$PY" &>/dev/null; then break; fi
done
echo "Using: $PY ($($PY --version 2>&1))"

# Create venv
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PY -m venv .venv || {
        echo "⚠  venv creation failed. On Ubuntu/Debian, run:"
        echo "   sudo apt install python3-venv python3-dev"
        echo "   Then re-run this script."
        exit 1
    }
fi

# Activate venv (works on both macOS and Linux)
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
else
    echo "⚠  venv activate script not found. Deleting .venv and retrying..."
    rm -rf .venv
    $PY -m venv .venv
    source .venv/bin/activate
fi
pip install --upgrade pip -q

# Platform-specific install
if [[ "$(uname)" == "Darwin" ]]; then
    echo "Installing Mac dependencies (mlx-whisper + Metal)..."
    pip install -r requirements-mac.txt -q

    # Check ffmpeg
    if ! command -v ffmpeg &>/dev/null; then
        echo "⚠  ffmpeg not found. Install with: brew install ffmpeg"
    fi
else
    echo "Installing Windows/Linux dependencies (faster-whisper)..."
    pip install -r requirements-win.txt -q
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "To run:"
echo "  cd $SCRIPT_DIR"
echo "  source .venv/bin/activate"
echo "  python typeoff.py"
echo ""
echo "First run will download the Whisper 'small' model (~500MB)."
echo "macOS: grant Accessibility + Microphone permissions when prompted."
