# Pinned by digest (#356): a tagged release rebuilds on exactly this base.
# Refresh deliberately (docker manifest inspect python:3.11-slim), not
# implicitly on every build.
FROM python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534

# uv (pinned) resolves from the committed lockfile — two builds of the
# same commit install byte-identical dependency sets.
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /uvx /bin/

WORKDIR /app

# Install system dependencies (including WeasyPrint requirements for PDF generation)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    postgresql-client \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from the lockfile (#356). The venv lives
# outside /app so a dev bind-mount of ./backend can't shadow it.
# --frozen: fail instead of silently re-resolving when uv.lock is stale.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PATH="/opt/venv/bin:$PATH"
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code, then install the project itself on top of the
# already-cached dependency layer.
COPY . .
RUN uv sync --frozen --no-dev

# Create non-root user and storage directory
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/storage \
    && chmod +x /app/docker-entrypoint.sh \
    && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
