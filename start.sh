#!/bin/bash
# start.sh

# Wait for MongoDB connection if needed
echo "Starting KUCCPS Courses Checker..."

# Run with gunicorn for better performance
gunicorn --bind 0.0.0.0:8080 \
    --workers 2 \
    --threads 4 \
    --worker-class gthread \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    "app:app"