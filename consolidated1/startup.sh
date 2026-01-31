#!/bin/bash

# 1. Force install dependencies on boot
echo "Installing dependencies..."
pip install -r requirements.txt

# 2. Start the Streamlit app
echo "Starting dashboard..."
python -m streamlit run consolidated1.py --server.port 8000 --server.address 0.0.0.0