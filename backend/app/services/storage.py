from __future__ import annotations

from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings


class StorageService:
    """Thin boto3 wrapper for storing resume files in S3/MinIO."""

    def __init__(
        self,
        endpoint_url: str | None,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str,
        presign_expiry: int = 3600,
    ) -> None:
        self.bucket = bucket
        self.presign_expiry = presign_expiry
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)

    def upload(self, key: str, fileobj: BinaryIO, content_type: str) -> None:
        self.client.upload_fileobj(
            fileobj,
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )

    def presigned_url(self, key: str) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=self.presign_expiry,
        )


def build_storage() -> StorageService:
    return StorageService(
        endpoint_url=settings.s3_endpoint_url,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        bucket=settings.s3_bucket,
        region=settings.s3_region,
    )
