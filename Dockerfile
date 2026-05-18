# Use official lightweight Python image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install uv globally
ENV UV_HTTP_TIMEOUT=300
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy uv lock files and install Python dependencies
COPY pyproject.toml uv.lock ./
RUN uv venv && uv pip install -e .

# Install Playwright browser (required for Dawn scraping)
ENV PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=300000
RUN uv run playwright install chromium --with-deps

# Copy project files
COPY . .

# Copy supervisor configuration
COPY deployment/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose FastAPI port
EXPOSE 8000

# NOTE: Mount the db directory as a volume to persist SQLite databases and WhatsApp auth:
#   docker run -v $(pwd)/db:/app/db ...
# Run 'python scripts/whatsapp_register.py' once on first deploy to generate the session file.

# Run supervisor (manages fastapi + scheduler)
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
