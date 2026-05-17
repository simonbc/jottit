"""gunicorn configuration for the production deploy."""

from __future__ import annotations

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
worker_class = "sync"
timeout = 30
access_logfile = "-"
error_logfile = "-"
