# Base image for all stages
FROM python:3.12.4-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    PYTHONPATH=/app

WORKDIR /app

# --- Stage 1: Build-ready Base ---
FROM base AS base-builder

# Combined system dependencies for all builders to simplify
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libmagic1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    poppler-utils \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Pre-pin numpy for consistency across parallel segments
RUN pip install "numpy==1.26.4"

# --- Stage 2b: Parallel NLP & Tools Builder ---
# This stage handles document parsing, spacy, and pii tools
FROM base-builder AS nlp-builder
RUN pip install --prefix=/install/nlp \
    "spacy==3.7.5" \
    "unstructured[pdf]==0.15.0" \
    "pypdf>=5.1.0" \
    "python-magic>=0.4.27" \
    "simhash>=2.0" \
    "yake>=0.4" \
    "better-profanity==0.7.0" \
    "presidio-analyzer>=2.2.351" \
    "presidio-anonymizer>=2.2.351"

# --- Stage 2c: Core API & Ecosystem Builder ---
# Fast to build, handles all the web and data clients
FROM base-builder AS core-builder
RUN pip install --prefix=/install/core \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.34" \
    "pydantic>=2.10" \
    "pydantic-settings>=2.7" \
    "python-dotenv>=1.0" \
    "python-multipart>=0.0.12" \
    "aiohttp>=3.10" \
    "requests==2.31.0" \
    "python-jose[cryptography]==3.3.0" \
    "openai==1.55.3" \
    "anthropic==0.40.0" \
    "tiktoken>=0.7" \
    "langchain>=0.2.0,<0.3.0" \
    "langchain-core>=0.2.0,<0.3.0" \
    "langchain-openai>=0.1.0,<0.2.0" \
    "langchain-community>=0.2.0,<0.3.0" \
    "langgraph>=0.1.0,<0.2.0" \
    "qdrant-client>=1.12" \
    "supabase>=2.13" \
    "upstash-redis>=1.2" \
    "cohere>=5.0.0" \
    "datasets>=2.19" \
    "pandas>=2.2" \
    "langfuse==2.57.12" \
    "ragas==0.1.21"

# --- Stage 3: Merge & Verify ---
FROM base-builder AS final-builder

# Merge parallel prefixes into the primary environment
# Note: ml-builder removed — reranking now uses Cohere Rerank API (saves ~1-2GB image size)
COPY --from=core-builder /install/core /usr/local
COPY --from=nlp-builder /install/nlp /usr/local

# Download only the small spaCy model (sm = 12MB vs lg = 400MB)
RUN python -m spacy download en_core_web_sm

# Final verification (torch removed from stack)
RUN python -c "import langgraph; import anthropic; import langchain; import jose; import cohere; print('All critical imports verified OK')"

# --- Stage 4: Production Runtime ---
FROM base AS runtime

# Copy only the system libraries required for runtime (libmagic1, poppler, etc)
# Since they are in /usr/lib or /lib, we rely on the final-builder state or re-install
# To keep it simple and robust, we use final-builder but clean it up.
COPY --from=final-builder /usr/local /usr/local

# Add the runtime system deps back (libmagic, libgl1, etc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libglib2.0-0 \
    poppler-utils \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
