import os
from typing import List, Dict, Any

import boto3


class QueueService:
    """Simple SQS helper wrapping a ``boto3`` SQS client."""

    def __init__(self, region_name: str | None = None):
        self.region_name = region_name or os.getenv("AWS_REGION", "us-east-2")
        self._client = boto3.client("sqs", region_name=self.region_name)

    # ------------------------------------------------------------------
    # Message helpers
    # ------------------------------------------------------------------

    def receive_messages(
        self,
        queue_url: str,
        max_messages: int = 1,
        wait_time_seconds: int = 10,
        visibility_timeout: int | None = None,
    ) -> List[Dict[str, Any]]:
        """Long-poll the queue and return up to *max_messages*.

        The call returns an **empty list** when no messages are available.
        """
        params: Dict[str, Any] = {
            "QueueUrl": queue_url,
            "MaxNumberOfMessages": max_messages,
            "WaitTimeSeconds": wait_time_seconds,
            "MessageAttributeNames": ["All"],
        }
        if visibility_timeout is not None:
            params["VisibilityTimeout"] = visibility_timeout
        resp = self._client.receive_message(**params)
        return resp.get("Messages", [])

    def delete_message(self, queue_url: str, receipt_handle: str) -> None:
        self._client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)

    def send_message(
        self, queue_url: str, message_body: str, message_attributes: Dict[str, Any] | None = None
    ) -> None:
        self._client.send_message(
            QueueUrl=queue_url,
            MessageBody=message_body,
            MessageAttributes=message_attributes or {},
        )

    # ------------------------------------------------------------------
    # Administration helpers
    # ------------------------------------------------------------------

    def get_queue_attributes(self, queue_url: str) -> Dict[str, str]:
        resp = self._client.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["All"])
        return resp.get("Attributes", {}) 