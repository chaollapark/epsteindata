#!/bin/bash
set -euo pipefail

echo "=== Epstein Scraper: vani3 Setup ==="

# Install EPEL for tesseract
echo "[1/4] Installing system packages..."
dnf install -y epel-release
dnf install -y python3-pip tesseract poppler-utils aria2 sqlite

# Install Python packages
echo "[2/4] Installing Python packages..."
pip3 install httpx PyYAML PyMuPDF

# Create data directories
echo "[3/4] Creating directory structure..."
mkdir -p /root/epstein/data
mkdir -p /root/epstein/data/extracted_text
mkdir -p /root/epstein/logs

# Verify installations
echo "[4/4] Verifying installations..."
python3 -c "import httpx; print(f'httpx {httpx.__version__}')"
python3 -c "import yaml; print(f'PyYAML OK')"
python3 -c "import fitz; print(f'PyMuPDF {fitz.version[0]}')"
tesseract --version | head -1
pdftoppm -v 2>&1 | head -1
aria2c --version | head -1

echo ""
echo "=== Setup complete ==="
