FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libglib2.0-0 \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10002 kbuser

WORKDIR /workspace/backend

RUN pip install --no-cache-dir uv

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend /workspace/backend

RUN mkdir -p /srv/knowledge/vector-store /srv/knowledge/workspace && chown -R kbuser:kbuser /workspace /srv/knowledge

USER kbuser

EXPOSE 8081

CMD ["uv", "run", "uvicorn", "knowledge.api.main:app", "--host", "0.0.0.0", "--port", "8081"]
