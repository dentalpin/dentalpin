"""S3-compatible object storage backend."""

import boto3
from botocore.exceptions import ClientError

from .base import StorageBackend

NOT_FOUND_CODES = {"NoSuchKey", "NotFound", "404"}


class S3StorageBackend(StorageBackend):
    """Store files in an S3 bucket (AWS S3 or any S3-compatible endpoint).

    Credentials fall back to the standard AWS chain (env vars, IAM
    profile) when explicit keys are absent.
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

    async def store(self, data: bytes, path: str) -> str:
        self.client.put_object(Bucket=self.bucket, Key=path, Body=data)
        return path

    async def retrieve(self, path: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=path)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in NOT_FOUND_CODES:
                raise FileNotFoundError(f"File not found: {path}") from exc
            raise
        return response["Body"].read()

    async def delete(self, path: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=path)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in NOT_FOUND_CODES:
                return False
            raise
        self.client.delete_object(Bucket=self.bucket, Key=path)
        return True

    async def exists(self, path: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=path)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in NOT_FOUND_CODES:
                return False
            raise
        return True
