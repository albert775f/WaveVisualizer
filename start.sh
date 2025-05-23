#!/bin/bash

# Create necessary directories if they don't exist
mkdir -p uploads/audio uploads/images output

# Set proper permissions
chmod -R 755 uploads output

# Set environment variables
export FLASK_APP=app.py
export FLASK_ENV=production
export DATABASE_URL="sqlite:///wavevisualizer.db"

# Install dependencies if needed
pip install -r requirements.txt

# Start the application with gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 300 --max-requests 1000 --max-requests-jitter 50 app:app 