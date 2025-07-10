import os
from typing import List

import boto3
from botocore.exceptions import ClientError, BotoCoreError


class S3Service:
    """Thin wrapper around ``boto3`` S3 client used by the PDF-processing worker.

    Keeping S3 operations in a dedicated helper class makes it easier to
    unit-test the processor (can be mocked) and avoids sprinkling low-level
    boto3 calls throughout the codebase.
    """

    def __init__(self, region_name: str | None = None):
        self.region_name = region_name or os.getenv("AWS_REGION", "us-east-2")
        # Re-use the default credential chain (env vars, IAM role, etc.)
        self._client = boto3.client("s3", region_name=self.region_name)

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------

    def download_file(self, bucket: str, key: str, local_path: str) -> None:
        """Download ``s3://bucket/key`` to ``local_path`` (overwrites)."""
        self._client.download_file(bucket, key, local_path)

    def upload_file(self, local_path: str, bucket: str, key: str) -> None:
        """Upload local file to S3 at the given bucket/key."""
        self._client.upload_file(local_path, bucket, key)

    def move_file(self, bucket: str, source_key: str, dest_key: str) -> None:
        """Move an object by *copy + delete* inside the same bucket."""
        copy_source = {"Bucket": bucket, "Key": source_key}
        try:
            self._client.copy(copy_source, bucket, dest_key)
            self._client.delete_object(Bucket=bucket, Key=source_key)
        except (ClientError, BotoCoreError) as exc:
            # Propagate; caller decides how to handle
            raise exc

    def delete_file(self, bucket: str, key: str) -> None:
        self._client.delete_object(Bucket=bucket, Key=key)

    def list_files(self, bucket: str, prefix: str = "") -> List[str]:
        paginator = self._client.get_paginator("list_objects_v2")
        keys: List[str] = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys 