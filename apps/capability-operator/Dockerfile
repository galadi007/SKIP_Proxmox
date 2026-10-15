FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY . .

RUN uv sync --frozen --package capability-operator --extra all

# Abhaengigkeiten und Plugins sind oben installiert; --no-sync verhindert, dass
# uv die src-Layout-Pakete (SDK, Plugins) bei jedem Start neu baut.
CMD ["uv", "run", "--no-sync", \
     "kopf", "run", "apps/capability-operator/main.py", "--standalone", "--all-namespaces"]
