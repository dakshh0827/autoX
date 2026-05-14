# Multi-stage build for optimal image size
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libxkbcommon0 \
    libdbus-1-3 \
    libfontconfig1 \
    libfreetype6 \
    libharfbuzz0b \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    fonts-dejavu-core \
    fonts-liberation \
    fonts-unifont \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install --default-timeout=1000 --retries 5 -r requirements.txt

# Install Playwright browser at build time using the system packages above
RUN playwright install chromium

# Copy application code
COPY . .

# Expose port (7860 for Hugging Face Spaces, 8000 for standard deployment)
EXPOSE 8000

# Health check disabled temporarily to avoid startup hangs in this environment
HEALTHCHECK NONE

# Set environment defaults for deployment (do NOT override PORT so platforms
# like Hugging Face Spaces can inject their required port, e.g. 7860)
ENV HOST=0.0.0.0 \\
    DEBUG=False \\
    BROWSER_HEADLESS=True

# Use simple uvicorn command for startup
CMD ["sh", "-c", "uvicorn main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
