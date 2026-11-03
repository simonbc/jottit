from __future__ import annotations

import secrets

from flask import abort, current_app, g, jsonify, make_response, request
from flask.typing import ResponseReturnValue

from jottit import auth
from jottit.db import get_request_conn, get_upload, new_upload
from jottit.storage import Storage

# Content types we accept, keyed by the extension we give the stored file.
_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
}

# Multipart boundaries and headers ride on top of the file itself.
_FORM_OVERHEAD_BYTES = 64 * 1024


def sniff_image_type(data: bytes) -> str | None:
    """Content type from the file's magic bytes, or None if it isn't an image we accept."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def upload(site_slug: str) -> ResponseReturnValue:
    """Store one image for the current site and return the URL to embed it at.

    The URL is site-relative (`/site/uploads/<name>`); `format_content`
    re-roots it for secret-URL sites and feeds.
    """
    if g.site is None:
        abort(404)
    if (response := auth.gate("edit")) is not None:
        return response

    max_bytes: int = current_app.config["MAX_UPLOAD_BYTES"]
    too_big = f"Images must be {max_bytes / 1024 / 1024:g} MB or smaller."
    if (request.content_length or 0) > max_bytes + _FORM_OVERHEAD_BYTES:
        return jsonify(error=too_big), 413

    file = request.files.get("file")
    if file is None:
        return jsonify(error="No image was uploaded."), 400
    data = file.read(max_bytes + 1)
    if len(data) > max_bytes:
        return jsonify(error=too_big), 413
    content_type = sniff_image_type(data)
    if content_type is None:
        return jsonify(error="Only PNG, JPEG, GIF, and WebP images can be uploaded."), 415

    name = f"{secrets.token_urlsafe(16)}.{_EXTENSIONS[content_type]}"
    storage_key = _storage_key(name)
    _storage().put(storage_key, data, content_type=content_type)
    new_upload(
        _conn(),
        site_id=g.site.id,
        storage_key=storage_key,
        filename=file.filename,
        content_type=content_type,
        size=len(data),
        ip=request.remote_addr,
    )
    return jsonify(url=f"/site/uploads/{name}"), 201


def serve(site_slug: str, name: str) -> ResponseReturnValue:
    """Proxy an uploaded image, readable by whoever can read the site's pages."""
    if g.site is None:
        abort(404)
    if (response := auth.gate("view")) is not None:
        return response

    row = get_upload(_conn(), site_id=g.site.id, storage_key=_storage_key(name))
    if row is None:
        abort(404)
    data = _storage().get(row.storage_key)
    if data is None:
        abort(404)

    response = make_response(data)
    response.headers["Content-Type"] = row.content_type
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Names are random and never reused, so the bytes behind a URL never
    # change. `private` keeps shared caches from holding images of
    # private sites.
    response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
    return response


def _storage_key(name: str) -> str:
    return f"sites/{g.site.id}/{name}"


def _storage() -> Storage:
    return current_app.extensions["storage"]


def _conn():
    conn = get_request_conn()
    if conn is None:
        abort(500)
    return conn
