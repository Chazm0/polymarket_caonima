#!/usr/bin/env bash

echo "Creating virtual environment..."
python -m venv .venv
source .venv/bin/activate

echo "Installing package..."
pip install --upgrade pip
pip install -e .

echo "Done. Activate with:"
echo "source .venv/bin/activate"