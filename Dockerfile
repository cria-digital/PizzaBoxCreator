FROM python:3.14-slim AS base

# System deps for Pillow (JPEG/TIFF), psycopg2, and PhotoshopAPI native lib.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo-dev \
    libtiff-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    zlib1g-dev \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache).
COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[gemini]"

# Copy application code.
COPY app/ app/
COPY alembic.ini ./
COPY alembic/ alembic/

# Create storage directories the app expects at runtime.
RUN mkdir -p storage/output storage/preview storage/thumbnails storage/logos temp

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
