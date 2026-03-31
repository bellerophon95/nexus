FROM python:3.12.4-slim

# Bust cache on every build to prevent stale layer issues
ARG CACHE_BUST=20240330

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    PYTHONPATH=/app

WORKDIR /app

# System dependencies
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

# --- Layer 1: Pin numpy early so every subsequent package builds against it ---
RUN pip install --no-cache-dir "numpy==1.26.4"

# --- Layer 2: Core web framework ---
RUN pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.34" \
    "pydantic>=2.10" \
    "pydantic-settings>=2.7" \
    "python-dotenv>=1.0" \
    "python-multipart>=0.0.12" \
    "aiohttp>=3.10" \
    "requests==2.31.0"

# --- Layer 3: AI / LLM clients ---
RUN pip install --no-cache-dir \
    "openai==1.55.3" \
    "anthropic==0.40.0" \
    "tiktoken>=0.7"

# --- Layer 4: LangChain ecosystem (pinned for ragas 0.1.21 compatibility) ---
RUN pip install --no-cache-dir \
    "langchain>=0.2.0,<0.3.0" \
    "langchain-core>=0.2.0,<0.3.0" \
    "langchain-openai>=0.1.0,<0.2.0" \
    "langchain-community>=0.2.0,<0.3.0" \
    "langgraph>=0.1.0,<0.2.0"

# --- Layer 5: Storage / data clients ---
RUN pip install --no-cache-dir \
    "qdrant-client>=1.12" \
    "supabase>=2.13" \
    "upstash-redis>=1.2" \
    "datasets>=2.19" \
    "pandas>=2.2"

# --- Layer 6: ML models (heavy, kept in its own layer) ---
RUN pip install --no-cache-dir \
    "torch>=2.0.0" \
    "transformers>=4.40.0" \
    "sentence-transformers>=3.0"

# --- Layer 7: NLP / document processing ---
RUN pip install --no-cache-dir \
    "spacy>=3.7" \
    "pypdf>=5.1.0" \
    "python-magic>=0.4.27" \
    "simhash>=2.0" \
    "yake>=0.4" \
    "better-profanity==0.7.0"

RUN pip install --no-cache-dir "unstructured[pdf]>=0.15"

# --- Layer 8: spaCy model ---
RUN python -m spacy download en_core_web_sm

# --- Layer 9: Observability & evaluation (can conflict — last so nothing breaks earlier layers) ---
RUN pip install --no-cache-dir "langfuse==2.57.12"
RUN pip install --no-cache-dir "ragas==0.1.21"

# --- Layer 10: PII / guardrails ---
RUN pip install --no-cache-dir \
    "presidio-analyzer>=2.2.351" \
    "presidio-anonymizer>=2.2.351"

# --- VERIFICATION: fail the build early if critical imports are missing ---
RUN python -c "import langgraph; import anthropic; import langchain; print('All critical imports verified OK')"

# --- Pre-download SentenceTransformer model ---
COPY scripts/download_models.py ./scripts/download_models.py
RUN python scripts/download_models.py

# --- Copy application code last (maximises layer cache reuse) ---
COPY . .

EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
