ARG APP_UID=1000
ARG APP_GID=1000
ARG BASE_IMAGE=nvidia/cuda:12.6.0-base-ubuntu24.04

FROM ${BASE_IMAGE} AS base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PATH="/app/.venv/bin:/root/.local/bin:${PATH}"
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    build-essential \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
  && rm -rf /var/lib/apt/lists/*

# Symlink python3 to python if needed
RUN if ! command -v python >/dev/null 2>&1; then ln -s "$(command -v python3)" /usr/local/bin/python; fi

# Install dependencies as root before creating user
# This ensures dependency layer is cached even when APP_UID/APP_GID changes
COPY pyproject.toml requirements.txt ./
RUN uv venv .venv --python python3 && \
    uv pip install --no-cache -r requirements.txt

# Create user after dependency installation to maximize cache efficiency
ARG APP_UID
ARG APP_GID
RUN groupadd -g "${APP_GID}" -o appuser \
  && useradd -m -u "${APP_UID}" -g appuser -o appuser

# Change ownership after user creation
RUN chown -R appuser:appuser /app

FROM base AS development

ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=development

COPY --chown=appuser:appuser . .

EXPOSE 8000

USER appuser

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS production

ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

COPY --chown=appuser:appuser . .

RUN apt-get purge -y --auto-remove build-essential \
  && rm -rf /var/lib/apt/lists/*

USER appuser

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
