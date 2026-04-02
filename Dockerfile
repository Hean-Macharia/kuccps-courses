# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install production dependencies only
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose port (Fly expects 8080)
EXPOSE 8080

# Start Gunicorn (adjust "app:app" to your Flask entrypoint)
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
