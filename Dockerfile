# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose port
EXPOSE 8080

# Run Flask app (adjust if your entrypoint is different)
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
