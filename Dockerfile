# Multi-stage build for optimal image size
FROM python:3.11-slim as base

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
    pip install -r requirements.txt

# Install Playwright browsers (skip deps since we've already installed them above)
RUN playwright install chromium

# Copy application code
COPY . .

# Expose port (7860 for Hugging Face Spaces, 8000 for standard deployment)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Set environment defaults for deployment
ENV HOST=0.0.0.0 \
    PORT=8000 \
    DEBUG=False \
    BROWSER_HEADLESS=True

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
