#!/bin/bash

# Create necessary directories if they don't exist
mkdir -p uploads/audio uploads/images output

# Set proper permissions
chmod -R 755 uploads output

# Set environment variables
export FLASK_APP=app.py
export FLASK_ENV=production
export DATABASE_URL="sqlite:///wavevisualizer.db"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=4  # Optimize OpenMP threading
export MKL_NUM_THREADS=4  # Optimize MKL threading
export NUMEXPR_NUM_THREADS=4  # Optimize NumExpr threading
export MemoryLimit=4G  # Erhöhe auf 4GB oder mehr

# Install dependencies if needed
pip install -r requirements.txt

# Start the application with optimized gunicorn settings
gunicorn --bind 0.0.0.0:5000 \
    --workers 4 \
    --threads 4 \
    --worker-class gthread \
    --timeout 300 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --worker-connections 1000 \
    --keep-alive 5 \
    --backlog 2048 \
    --log-level info \
    app:app 