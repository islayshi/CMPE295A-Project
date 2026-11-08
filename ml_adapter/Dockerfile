# ==============================================================================
# Fight Fire With AI - FastAPI Machine Learning Adapter Container
# ==============================================================================
# Microservice bridge coordinating U-Net and PIML inference microservices.
# Listens on port ${PORT:-8001}.
# ==============================================================================

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8001

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app/

RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m adapter && \
    chown -R adapter:appgroup /app

USER adapter

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 2

