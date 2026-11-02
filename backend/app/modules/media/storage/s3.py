"""S3-compatible object storage backend."""

import asyncio
from contextlib import closing

import boto3
from botocore.exceptions import ClientError

from .base import StorageBackend

NOT_FOUND_CODES = {"NoSuchKey", "NotFound", "404"}


class S3StorageBackend(StorageBackend):
    """Store files in an S3 bucket (AWS S3 or any S3-compatible endpoint).

    Credentials fall back to the standard AWS chain (env vars, IAM
    profile) when explicit keys are absent. SDK calls run through
    asyncio.to_thread so the boto3 client's sync HTTP round trips do
    not block the event loop (ADR 0012 prescribes non-blocking storage
    IO; boto3 keeps aioboto3's dependency chain out).
    """

    def __init__(
        self,
        bucket: str,
        region: str = "",
        endpoint_url: str = "",
        access_key_id: str = "",
        secret_access_key: str = "",
    ) -> None:
        self.bucket = bucket
        session = boto3.Session(
            region_name=region or None,
            aws_access_key_id=access_key_id or None,
            aws_secret_access_key=secret_access_key or None,
        )
        client_kwargs: dict[str, object] = {}
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
        self.client = session.client("s3", **client_kwargs)

    def _not_found(self, exc: ClientError) -> bool:
        code = exc.response.get("Error", {}).get("Code")
        return code in NOT_FOUND_CODES

    async def store(self, data: bytes, path: str) -> str:
        await asyncio.to_thread(self.client.put_object, Bucket=self.bucket, Key=path, Body=data)
        return path

    async def retrieve(self, path: str) -> bytes:
        try:
            response = await asyncio.to_thread(self.client.get_object, Bucket=self.bucket, Key=path)
        except ClientError as exc:
            if self._not_found(exc):
                raise FileNotFoundError(f"File not found: {path}") from exc
            raise
        # StreamingBody holds a pooled connection; close it even when the
        # caller never drains the full body.
        with closing(response["Body"]):
            return response["Body"].read()

    async def delete(self, path: str) -> bool:
        try:
            await asyncio.to_thread(self.client.head_object, Bucket=self.bucket, Key=path)
        except ClientError as exc:
            if self._not_found(exc):
                return False
            raise
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=path)
        return True

    async def exists(self, path: str) -> bool:
        try:
            await asyncio.to_thread(self.client.head_object, Bucket=self.bucket, Key=path)
        except ClientError as exc:
            if self._not_found(exc):
                return False
            raise
        return True
