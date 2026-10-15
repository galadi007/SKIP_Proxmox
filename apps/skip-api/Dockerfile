FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY . .

RUN uv sync --frozen --package skip-api

EXPOSE 8000

CMD ["uv", "run", "--frozen", "--package", "skip-api", "uvicorn", "main:app", "--app-dir", "--reload", "apps/skip-api", "--host", "0.0.0.0", "--port", "8000"]
