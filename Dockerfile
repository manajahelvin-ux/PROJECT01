# ==========================================
# DataExtract AI - Dockerfile
# ==========================================
# Multi-stage build for production

# --- Base Stage ---
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements/ ./requirements/
RUN pip install --no-cache-dir -r requirements/prod.txt

# Install Playwright and browser dependencies
RUN playwright install --with-deps chromium

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput --settings=config.settings.prod || true

# --- Development Stage ---
FROM base AS development

RUN pip install --no-cache-dir -r requirements/dev.txt

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# --- Production Stage ---
FROM base AS production

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
