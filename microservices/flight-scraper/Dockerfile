FROM python:3.11-slim

LABEL maintainer="Agencia de Viajes"
LABEL service="flight-scraper"
LABEL version="1.0.0"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5001/health').raise_for_status()"

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "4", "--timeout", "120", "app:create_app()"]
