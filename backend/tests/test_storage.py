import io

import boto3
import pytest
from moto import mock_aws

from app.services.storage import StorageService


@pytest.fixture
def storage():
    with mock_aws():
        svc = StorageService(
            endpoint_url=None,
            access_key="testing",
            secret_key="testing",
            bucket="test-bucket",
            region="us-east-1",
        )
        svc.ensure_bucket()
        yield svc


def test_ensure_bucket_is_idempotent(storage):
    storage.ensure_bucket()  # second call should not raise
    s3 = boto3.client("s3", region_name="us-east-1")
    buckets = [b["Name"] for b in s3.list_buckets()["Buckets"]]
    assert "test-bucket" in buckets


def test_upload_stores_object(storage):
    storage.upload("leads/abc/cv.pdf", io.BytesIO(b"hello"), "application/pdf")
    s3 = boto3.client("s3", region_name="us-east-1")
    obj = s3.get_object(Bucket="test-bucket", Key="leads/abc/cv.pdf")
    assert obj["Body"].read() == b"hello"
    assert obj["ContentType"] == "application/pdf"


def test_presigned_url_points_at_object(storage):
    storage.upload("leads/abc/cv.pdf", io.BytesIO(b"hi"), "application/pdf")
    url = storage.presigned_url("leads/abc/cv.pdf")
    assert "leads/abc/cv.pdf" in url
    assert "test-bucket" in url
    assert "Signature" in url or "X-Amz-Signature" in url
