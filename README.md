# Jottit

Jottit makes getting a website as easy as filling out a textbox. Each site lives at its own subdomain (`myblog.jottit.org`) or its own secret URL (`jottit.org/abc12/`).

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

# Create the schema (one-time, until M8 lands Alembic migrations)
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

LGPLv3 — see [License.txt](License.txt).
