# Jottit

Jottit makes getting a website as easy as filling out a textbox. Each site lives at its own subdomain (`myblog.jottit.org`) or its own secret URL (`jottit.org/abc12/`).

This is a modern port of the 2007 Jottit codebase originally written by Simon Carstensen and Aaron Swartz. The Python 2 + web.py + Jinja 1 + psycopg2 stack has been rewritten on Flask 3 + SQLAlchemy Core 2 + Jinja2 + psycopg3, with the original look-and-feel preserved.

## Running locally

You'll need [uv](https://docs.astral.sh/uv/) and Postgres.

```sh
# Install Postgres and start it
brew install postgresql@16
brew services start postgresql@16

# Create the dev database
createdb jottit_dev

# Install Python dependencies
uv sync

# Configure your environment
cp .env.example .env

# Create the schema (Alembic migrations are tracked in M10)
uv run --env-file .env python -c "from jottit.db import make_engine, metadata; import os; metadata.create_all(make_engine(os.environ['DATABASE_URL']))"

# Run the dev server
uv run flask --app jottit run --port 5000
```

Open <http://localtest.me:5000>. The default `JOTTIT_DOMAIN=localtest.me:5000` uses [localtest.me](http://readme.localtest.me/) — `*.localtest.me` resolves to `127.0.0.1` — so subdomain routing works without any `/etc/hosts` edits.

## Tests

```sh
uv run pytest
```

Tests spin up a fresh `jottit_test` database against your local Postgres, run, and drop it at the end.

## License

AGPLv3 — see [LICENSE.md](LICENSE.md) and [NOTICE](NOTICE) for the relicensing path from the 2007 LGPLv3 original.
