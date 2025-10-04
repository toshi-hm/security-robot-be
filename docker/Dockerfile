FROM python:3.11-slim

ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Install uv for environment management
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

COPY . .

# Use uv to install project dependencies inside the image
RUN uv pip install --system --no-cache -r requirements.txt

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
