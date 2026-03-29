# Nexus Backend v1.2.3 - Preserve Package Structure
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libmagic1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install numpy first to satisfy build-time dependencies
RUN pip install --no-cache-dir numpy==1.26.4

# Install python dependencies - path adjusted for root context
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend as a package under /app/backend/ to preserve import paths
# Local code uses: from backend.api import ..., from backend.config import ...
COPY backend/ ./backend/

# Expose port and start application
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
