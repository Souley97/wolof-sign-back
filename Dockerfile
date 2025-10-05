
# Single stage build
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    python3-dev \
    postgresql-client \
    libpq5 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements_prod.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements_prod.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p media staticfiles logs

# Create user with explicit UID/GID
RUN adduser --disabled-password --gecos '' --uid 1000 altoppe && \
    chown -R altoppe:altoppe /app

# Switch to altoppe user
USER altoppe

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Start command
CMD ["gunicorn", "altoppe.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
