"""Blob storage for uploaded images.

Two backends share one tiny interface: `LocalStorage` writes files under a
directory (dev + tests), `S3Storage` talks to any S3-compatible bucket
(Tigris on Fly in production). `storage_from_env` picks S3 when
`BUCKET_NAME` is set — the variable `fly storage create` exports — and the
local directory otherwise.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Protocol

import boto3
from botocore.exceptions import ClientError


class Storage(Protocol):
    def put(self, key: str, data: bytes, *, content_type: str) -> None: ...

    def get(self, key: str) -> bytes | None:
        """Return the stored bytes, or None when the key doesn't exist."""
        ...


class LocalStorage:
    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError(f"storage key escapes the storage root: {key!r}")
        return path

    def put(self, key: str, data: bytes, *, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.is_file() else None


class S3Storage:
    def __init__(self, bucket: str, client: Any) -> None:
        self.bucket = bucket
        self.client = client

    def put(self, key: str, data: bytes, *, content_type: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes | None:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                return None
            raise
        return response["Body"].read()


def storage_from_env(default_root: str | os.PathLike[str]) -> Storage:
    """S3 when `BUCKET_NAME` is set, else files under `JOTTIT_UPLOADS_DIR` or `default_root`.

    Credentials come from `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`,
    which boto3 reads on its own.
    """
    bucket = os.environ.get("BUCKET_NAME")
    if bucket:
        client = boto3.client(
            "s3",
            endpoint_url=os.environ.get("AWS_ENDPOINT_URL_S3") or None,
            region_name=os.environ.get("AWS_REGION") or "auto",
        )
        return S3Storage(bucket, client)
    return LocalStorage(os.environ.get("JOTTIT_UPLOADS_DIR") or default_root)
