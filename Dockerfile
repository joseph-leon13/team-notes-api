# Team Notes API container image.
# Dependencies come from uv.lock, so the image runs exactly the versions the tests ran.
FROM python:3.12-slim

# uv binary from Astral's official image (pinned minor version)
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    NOTES_DATABASE_URL=sqlite:////data/notes.db

WORKDIR /app

# 1) Install third-party dependencies first (cached unless the lock file changes)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# 2) Install the application itself, plus the schema migrations
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync --frozen --no-dev

# Run as an unprivileged user; SQLite lives on a mountable volume
RUN useradd --create-home --uid 10001 app && mkdir -p /data && chown app:app /data
USER app
VOLUME ["/data"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"

# Apply pending migrations, then serve. `exec` hands PID 1 to uvicorn so signals work.
CMD ["sh", "-c", "/app/.venv/bin/alembic upgrade head && exec /app/.venv/bin/uvicorn team_notes_api.main:create_app --factory --host 0.0.0.0 --port 8000"]
