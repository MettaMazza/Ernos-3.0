# ─── Ernos 3.0 — Secured Docker Image ───
# Multi-stage: deps → encrypt prompts → compile bytecode → runtime

FROM python:3.11-slim AS builder

# System dependencies for native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Install cryptography for build-time encryption
RUN pip install --no-cache-dir cryptography

# Copy source
COPY src/ src/
COPY config/ config/
COPY scripts/ scripts/
COPY pytest.ini .

# ── Security Layer 1: Encrypt prompts ──
RUN PYTHONPATH=/build python scripts/encrypt_assets.py \
    && find src/prompts/ -name "*.txt" -delete \
    && echo "✅ Prompts encrypted, .txt originals deleted"

# ── Security Layer 2: Compile to bytecode and strip source ──
RUN python -m compileall -b -q src/ config/ \
    && find src/ config/ -name "*.py" -delete \
    && echo "✅ Python compiled to bytecode, .py source deleted"

# ── Clean build artifacts ──
RUN rm -rf scripts/ __pycache__

# ─── Runtime image ───
FROM python:3.11-slim

# Runtime dependencies (playwright, ffmpeg, espeak)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy compiled bytecode (no .py source)
COPY --from=builder /build/src/ src/
COPY --from=builder /build/config/ config/
COPY --from=builder /build/pytest.ini .

# Copy non-Python assets (JS files not handled by compileall)
COPY src/gaming/mineflayer/ src/gaming/mineflayer/
COPY src/visualization/ src/visualization/

# Install Playwright browsers
RUN playwright install --with-deps chromium 2>/dev/null || true

# Data volume mount point
VOLUME /data

# Default data directory — maps to /data volume mount
ENV ERNOS_DATA_DIR=/data
ENV PYTHONPATH=/app

# Web server port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

ENTRYPOINT ["python", "src/main.py"]
