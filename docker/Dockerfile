ARG APP_UID=1000
ARG APP_GID=1000

FROM python:3.12-slim AS base

ENV PATH="/app/.venv/bin:/root/.local/bin:${PATH}"
WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    build-essential \
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

ARG APP_UID
ARG APP_GID
RUN groupadd -g "${APP_GID}" -o appuser \
  && useradd -m -u "${APP_UID}" -g appuser -o appuser

COPY pyproject.toml requirements.txt ./
RUN uv venv .venv && \
    uv pip install --no-cache -r requirements.txt
RUN chown -R appuser:appuser /app

FROM base AS development

ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=development

COPY --chown=appuser:appuser . .

EXPOSE 8000

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS production

ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

COPY --chown=appuser:appuser . .

RUN apt-get purge -y --auto-remove build-essential \
  && rm -rf /var/lib/apt/lists/*

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
