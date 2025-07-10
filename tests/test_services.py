import json
from botocore.stub import Stubber, ANY
import boto3

from s3_service import S3Service
from queue_service import QueueService
from processor import PDFProcessor
import processor as processor_module
from unittest.mock import MagicMock


def test_s3_move_file_stub():
    s3 = S3Service(region_name="us-east-2")
    stubber = Stubber(s3._client)

    # Stub copy and delete operations performed inside move_file
    stubber.add_response(
        "copy_object",
        {},
        {
            "Bucket": "my-bucket",
            "CopySource": {"Bucket": "my-bucket", "Key": "src"},
            "Key": "dest",
        },
    )
    stubber.add_response(
        "delete_object",
        {},
        {"Bucket": "my-bucket", "Key": "src"},
    )

    stubber.activate()
    s3.move_file("my-bucket", "src", "dest")
    stubber.deactivate()


def test_queue_receive_messages_stub():
    qs = QueueService(region_name="us-east-2")
    stubber = Stubber(qs._client)

    # Return empty set of messages
    stubber.add_response("receive_message", {}, {
        "QueueUrl": "https://sqs.us-east-2.amazonaws.com/123/queue",
        "MaxNumberOfMessages": 1,
        "WaitTimeSeconds": 10,
        "MessageAttributeNames": ["All"],
    })

    stubber.activate()
    msgs = qs.receive_messages("https://sqs.us-east-2.amazonaws.com/123/queue", max_messages=1)
    assert msgs == []
    stubber.deactivate()


def test_processor_parses_s3_event():
    # Use stubbed S3 and SQS to avoid network
    s3 = S3Service(region_name="us-east-2")
    qs = QueueService(region_name="us-east-2")

    # No-op patch to avoid complex transfer stubbing
    s3.move_file = lambda *args, **kwargs: None  # type: ignore
    s3.download_file = lambda *args, **kwargs: None  # type: ignore

    # Patch QueueService.delete_message to no-op
    qs.delete_message = lambda *args, **kwargs: None  # type: ignore
    qs.receive_messages = lambda *a, **k: []  # Not used but for completeness

    # Patch heavy sentence-transformer in processor module
    processor_module.dedup_model = MagicMock()
    processor_module.dedup_model.encode.return_value = None
    proc = PDFProcessor(s3_service=s3, queue_service=qs, bucket_name="bucket", queue_url="url")

    sample_event = {
        "Body": json.dumps({
            "Records": [{
                "s3": {
                    "bucket": {"name": "bucket"},
                    "object": {"key": "incoming/test.pdf", "size": 1000}
                }
            }]
        })
    }

    # The method should not raise – we don't assert DB side-effects here
    proc._process_queue_message(sample_event)

    # No exceptions means pass 