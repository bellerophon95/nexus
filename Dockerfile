FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    libmagic-dev \
    poppler-utils \
    tesseract-ocr \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Copy project files
COPY pyproject.toml poetry.lock* ./

# Install dependencies directly from pyproject.toml
# This bypasses the Poetry solver loops often occurring on Render
RUN pip install .

# Pre-download ML models for stability and speed
# 1. Download spaCy model
RUN python -m spacy download en_core_web_sm

# 2. Download SentenceTransformer models
# We copy the download script early to leverage layer caching for models
COPY scripts/download_models.py ./scripts/download_models.py
RUN python scripts/download_models.py

# Copy application code
COPY . .

# Expose port (Render ignores EXPOSE, but good practice)
EXPOSE 8000

# Run the application with dynamic PORT
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
