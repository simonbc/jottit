FROM python:3.12-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md LICENSE.md ./
COPY jottit ./jottit

RUN uv sync --frozen --no-dev


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8000

RUN groupadd --system --gid 1000 jottit \
    && useradd --system --uid 1000 --gid jottit --home-dir /app --shell /bin/bash jottit \
    && mkdir -p /app \
    && chown jottit:jottit /app

WORKDIR /app

COPY --from=builder --chown=jottit:jottit /app/.venv /app/.venv
COPY --chown=jottit:jottit alembic.ini ./
COPY --chown=jottit:jottit migrations ./migrations
COPY --chown=jottit:jottit jottit ./jottit
COPY --chown=jottit:jottit gunicorn.conf.py ./
COPY --chown=jottit:jottit scripts ./scripts

USER jottit

EXPOSE 8000

ENTRYPOINT ["scripts/start.sh"]
