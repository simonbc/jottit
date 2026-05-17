#!/usr/bin/env bash
set -euo pipefail

# Argument escape hatch: `docker run jottit alembic ...` etc.
if [ $# -gt 0 ]; then
    exec "$@"
fi

alembic upgrade head
exec gunicorn -c gunicorn.conf.py "jottit:create_app()"
