"""S3 storage backend + factory selection tests.

No S3 endpoint is contacted: the client is a stub recording calls, so
each test asserts the backend's contract (store/retrieve/delete/exists
semantics and error mapping) without network access.
"""

import pytest
from botocore.exceptions import ClientError

from app.modules.media.storage import get_storage_backend
from app.modules.media.storage.local import LocalStorageBackend
from app.modules.media.storage.s3 import S3StorageBackend

NOT_FOUND_CASES = ["NoSuchKey", "NotFound", "404"]


class StubS3Client:
    """Minimal stand-in for a boto3 S3 client.

    Every lookup for a missing key raises a ClientError carrying
    ``error_code`` (default NoSuchKey), mirroring botocore's
    Error.Code-based dispatch.
    """

    def __init__(
        self,
        objects: dict[str, bytes] | None = None,
        error_code: str = "NoSuchKey",
    ) -> None:
        self.objects: dict[str, bytes] = objects or {}
        self.error_code = error_code
        self.put_calls: list[tuple[str, bytes]] = []
        self.delete_calls: list[str] = []
        self.head_calls: list[str] = []

    def _missing(self, key: str, operation: str) -> ClientError:
        return ClientError({"Error": {"Code": self.error_code, "Message": "stub"}}, operation)

    def put_object(self, **kwargs: object) -> None:
        key = str(kwargs["Key"])
        body = kwargs["Body"]
        self.put_calls.append((key, body))
        self.objects[key] = body

    def head_object(self, **kwargs: object) -> dict:
        key = str(kwargs["Key"])
        self.head_calls.append(key)
        if key not in self.objects:
            raise self._missing(key, "HeadObject")
        return {"ContentLength": len(self.objects[key])}

    def get_object(self, **kwargs: object) -> dict:
        key = str(kwargs["Key"])
        if key not in self.objects:
            raise self._missing(key, "GetObject")
        body = _StubBody(self.objects[key])
        self.last_body = body
        return {"Body": body}

    def delete_object(self, **kwargs: object) -> dict:
        key = str(kwargs["Key"])
        self.delete_calls.append(key)
        self.objects.pop(key, None)
        return {"ResponseMetadata": {"HTTPStatusCode": 204}}


class _StubBody:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self.closed = False

    def read(self) -> bytes:
        return self._data

    def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_retrieve_closes_the_body() -> None:
    client = StubS3Client({"k": b"v"})
    backend = _make_backend(client)

    assert await backend.retrieve("k") == b"v"
    assert client.last_body.closed is True


def _make_backend(client: StubS3Client) -> S3StorageBackend:
    backend = S3StorageBackend.__new__(S3StorageBackend)
    backend.bucket = "test-bucket"
    backend.client = client
    return backend


@pytest.mark.asyncio
async def test_store_puts_object_and_returns_path() -> None:
    client = StubS3Client()
    backend = _make_backend(client)

    stored = await backend.store(b"hello", "clinic-a/doc.pdf")

    assert stored == "clinic-a/doc.pdf"
    assert client.put_calls == [("clinic-a/doc.pdf", b"hello")]


@pytest.mark.asyncio
async def test_retrieve_returns_body_bytes() -> None:
    backend = _make_backend(StubS3Client({"clinic-a/doc.pdf": b"payload"}))

    data = await backend.retrieve("clinic-a/doc.pdf")

    assert data == b"payload"


@pytest.mark.asyncio
@pytest.mark.parametrize("code", NOT_FOUND_CASES)
async def test_retrieve_missing_maps_every_not_found_code(code: str) -> None:
    backend = _make_backend(StubS3Client(error_code=code))

    with pytest.raises(FileNotFoundError):
        await backend.retrieve("missing.pdf")


@pytest.mark.asyncio
async def test_delete_existing_returns_true_and_removes() -> None:
    client = StubS3Client({"x.pdf": b"1"})
    backend = _make_backend(client)

    assert await backend.delete("x.pdf") is True
    assert client.delete_calls == ["x.pdf"]


@pytest.mark.asyncio
@pytest.mark.parametrize("code", NOT_FOUND_CASES)
async def test_delete_missing_returns_false_for_every_not_found_code(
    code: str,
) -> None:
    client = StubS3Client(error_code=code)
    backend = _make_backend(client)

    assert await backend.delete("missing.pdf") is False
    assert client.delete_calls == []


@pytest.mark.asyncio
async def test_exists_true_when_head_succeeds() -> None:
    backend = _make_backend(StubS3Client({"x.pdf": b"1"}))

    assert await backend.exists("x.pdf") is True


@pytest.mark.asyncio
@pytest.mark.parametrize("code", NOT_FOUND_CASES)
async def test_exists_false_for_every_not_found_code(code: str) -> None:
    backend = _make_backend(StubS3Client(error_code=code))

    assert await backend.exists("missing.pdf") is False


@pytest.mark.asyncio
async def test_retrieve_propagates_unexpected_client_error() -> None:
    backend = _make_backend(StubS3Client(error_code="AccessDenied"))

    with pytest.raises(ClientError):
        await backend.retrieve("missing.pdf")


@pytest.mark.asyncio
async def test_exists_propagates_unexpected_client_error() -> None:
    backend = _make_backend(StubS3Client(error_code="AccessDenied"))

    with pytest.raises(ClientError):
        await backend.exists("missing.pdf")


@pytest.mark.asyncio
async def test_delete_propagates_unexpected_client_error() -> None:
    client = StubS3Client(error_code="AccessDenied")
    backend = _make_backend(client)

    with pytest.raises(ClientError):
        await backend.delete("missing.pdf")
    assert client.delete_calls == []


def test_constructor_wires_session_and_client(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeSession:
        def __init__(self, **kwargs: object) -> None:
            captured["session"] = kwargs

        def client(self, service: str, **kwargs: object) -> StubS3Client:
            captured["service"] = service
            captured["client"] = kwargs
            return StubS3Client()

    monkeypatch.setattr("app.modules.media.storage.s3.boto3.Session", FakeSession)

    S3StorageBackend(
        bucket="ctl-bucket",
        region="eu-central-1",
        endpoint_url="http://minio:9000",
        access_key_id="ak",
        secret_access_key="sk",
    )

    assert captured["service"] == "s3"
    assert captured["session"] == {
        "region_name": "eu-central-1",
        "aws_access_key_id": "ak",
        "aws_secret_access_key": "sk",
    }
    assert captured["client"] == {"endpoint_url": "http://minio:9000"}


def test_constructor_uses_defaults_for_empty_fields(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeSession:
        def __init__(self, **kwargs: object) -> None:
            captured["session"] = kwargs

        def client(self, service: str, **kwargs: object) -> StubS3Client:
            captured["client"] = kwargs
            return StubS3Client()

    monkeypatch.setattr("app.modules.media.storage.s3.boto3.Session", FakeSession)

    S3StorageBackend(bucket="ctl-bucket")

    assert captured["session"] == {
        "region_name": None,
        "aws_access_key_id": None,
        "aws_secret_access_key": None,
    }
    assert captured["client"] == {}


def test_factory_builds_local_backend_for_local() -> None:
    backend = get_storage_backend()

    assert isinstance(backend, LocalStorageBackend)


def test_factory_builds_s3_backend_for_s3(monkeypatch) -> None:
    monkeypatch.setattr("app.modules.media.storage.settings.STORAGE_BACKEND", "s3")
    monkeypatch.setattr("app.modules.media.storage.settings.STORAGE_S3_BUCKET", "unit-bucket")
    get_storage_backend.cache_clear()

    backend = get_storage_backend()

    assert isinstance(backend, S3StorageBackend)
    assert backend.bucket == "unit-bucket"

    # Restore local dispatch for other tests (test-local cache-cleared).
    monkeypatch.undo()
    get_storage_backend.cache_clear()


def test_factory_requires_bucket_for_s3(monkeypatch) -> None:
    from app.config import Settings

    settings = Settings(TESTING="true", SECRET_KEY="test-secret-key-0123456789abcdef")
    settings.STORAGE_BACKEND = "s3"
    settings.STORAGE_S3_BUCKET = ""
    monkeypatch.setattr("app.modules.media.storage.settings", settings)
    get_storage_backend.cache_clear()

    with pytest.raises(ValueError, match="STORAGE_S3_BUCKET"):
        get_storage_backend()

    get_storage_backend.cache_clear()


def test_factory_raises_on_unknown_backend(monkeypatch) -> None:
    from app.config import Settings

    settings = Settings(TESTING="true", SECRET_KEY="test-secret-key-0123456789abcdef")
    settings.STORAGE_BACKEND = "carrier-pigeon"
    monkeypatch.setattr("app.modules.media.storage.settings", settings)
    get_storage_backend.cache_clear()

    with pytest.raises(ValueError, match="Unknown storage backend"):
        get_storage_backend()

    get_storage_backend.cache_clear()
