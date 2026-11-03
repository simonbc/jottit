from __future__ import annotations

import io
from pathlib import Path

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from jottit.storage import LocalStorage, S3Storage, storage_from_env

# ---- LocalStorage ----


def test_local_round_trip(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)

    storage.put("sites/1/a.png", b"png-bytes", content_type="image/png")

    assert storage.get("sites/1/a.png") == b"png-bytes"
    assert (tmp_path / "sites" / "1" / "a.png").read_bytes() == b"png-bytes"


def test_local_missing_key_returns_none(tmp_path: Path) -> None:
    assert LocalStorage(tmp_path).get("sites/1/missing.png") is None


def test_local_refuses_keys_outside_root(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "root")

    with pytest.raises(ValueError):
        storage.put("../escape.png", b"x", content_type="image/png")
    with pytest.raises(ValueError):
        storage.get("../../etc/passwd")


# ---- S3Storage (botocore Stubber; never touches the network) ----


def _stubbed_client():
    client = boto3.client(
        "s3",
        region_name="auto",
        endpoint_url="https://fly.storage.tigris.dev",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    return client, Stubber(client)


def test_s3_put_sends_bucket_key_body_and_type() -> None:
    client, stubber = _stubbed_client()
    stubber.add_response(
        "put_object",
        {},
        {
            "Bucket": "jottit-uploads",
            "Key": "sites/1/a.png",
            "Body": b"png-bytes",
            "ContentType": "image/png",
        },
    )

    with stubber:
        S3Storage("jottit-uploads", client).put(
            "sites/1/a.png", b"png-bytes", content_type="image/png"
        )

    stubber.assert_no_pending_responses()


def test_s3_get_returns_body() -> None:
    client, stubber = _stubbed_client()
    stubber.add_response(
        "get_object",
        {"Body": StreamingBody(io.BytesIO(b"png-bytes"), len(b"png-bytes"))},
        {"Bucket": "jottit-uploads", "Key": "sites/1/a.png"},
    )

    with stubber:
        data = S3Storage("jottit-uploads", client).get("sites/1/a.png")

    assert data == b"png-bytes"


def test_s3_get_missing_key_returns_none() -> None:
    client, stubber = _stubbed_client()
    stubber.add_client_error("get_object", service_error_code="NoSuchKey", http_status_code=404)

    with stubber:
        assert S3Storage("jottit-uploads", client).get("sites/1/missing.png") is None


def test_s3_get_other_errors_propagate() -> None:
    client, stubber = _stubbed_client()
    stubber.add_client_error("get_object", service_error_code="AccessDenied", http_status_code=403)

    with stubber, pytest.raises(Exception, match="AccessDenied"):
        S3Storage("jottit-uploads", client).get("sites/1/a.png")


# ---- storage_from_env ----


def test_storage_from_env_defaults_to_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("BUCKET_NAME", raising=False)
    monkeypatch.delenv("JOTTIT_UPLOADS_DIR", raising=False)

    storage = storage_from_env(tmp_path)

    assert isinstance(storage, LocalStorage)
    assert storage.root == tmp_path


def test_storage_from_env_honors_uploads_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("BUCKET_NAME", raising=False)
    monkeypatch.setenv("JOTTIT_UPLOADS_DIR", str(tmp_path / "custom"))

    storage = storage_from_env(tmp_path)

    assert isinstance(storage, LocalStorage)
    assert storage.root == tmp_path / "custom"


def test_storage_from_env_uses_tigris_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BUCKET_NAME", "jottit-uploads")
    monkeypatch.setenv("AWS_ENDPOINT_URL_S3", "https://fly.storage.tigris.dev")
    monkeypatch.setenv("AWS_REGION", "auto")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "tid_test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "tsec_test")

    storage = storage_from_env(tmp_path)

    assert isinstance(storage, S3Storage)
    assert storage.bucket == "jottit-uploads"
    assert storage.client.meta.endpoint_url == "https://fly.storage.tigris.dev"
    assert storage.client.meta.region_name == "auto"
