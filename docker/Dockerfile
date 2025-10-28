# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

ENV PATH="/root/.local/bin:${PATH}"
WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    build-essential \
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml requirements.txt ./
RUN uv pip install --system --no-cache -r requirements.txt

FROM base AS development

ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=development

COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS production

ARG APP_UID=1000
ARG APP_GID=1000

ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

COPY . .

RUN apt-get purge -y --auto-remove build-essential \
  && rm -rf /var/lib/apt/lists/*

RUN groupadd -g "${APP_GID}" -o appuser \
  && useradd -m -u "${APP_UID}" -g appuser -o appuser \
  && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
