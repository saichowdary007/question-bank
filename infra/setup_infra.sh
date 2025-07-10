#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Provision AWS resources required by the PDF Question-Bank pipeline.
#
# Prerequisites:
#   • AWS CLI must be configured (aws configure) with sufficient permissions.
#   • Variables below can be overridden via environment variables.
# -----------------------------------------------------------------------------

set -euo pipefail

REGION=${AWS_REGION:-us-east-2}
BUCKET_NAME=${S3_BUCKET_NAME:-pdf-question-bank}
QUEUE_NAME=${SQS_QUEUE_NAME:-pdf-processing-queue}
DLQ_NAME=${SQS_DLQ_NAME:-pdf-processing-dlq}

# Create S3 bucket (ignore if already exists)
aws s3 mb "s3://${BUCKET_NAME}" --region "$REGION" || true

# Enable bucket versioning
aws s3api put-bucket-versioning \
  --bucket "$BUCKET_NAME" \
  --versioning-configuration Status=Enabled

# Create DLQ and capture its ARN
DLQ_URL=$(aws sqs create-queue --queue-name "$DLQ_NAME" --query QueueUrl --output text)
DLQ_ARN=$(aws sqs get-queue-attributes \
  --queue-url "$DLQ_URL" \
  --attribute-names QueueArn \
  --query 'Attributes.QueueArn' --output text)

echo "Created/using DLQ $DLQ_URL ($DLQ_ARN)"

# Create main queue with dead-letter redrive policy
REDRIVE_POLICY="{\"deadLetterTargetArn\":\"${DLQ_ARN}\",\"maxReceiveCount\":\"3\"}"
QUEUE_URL=$(aws sqs create-queue \
  --queue-name "$QUEUE_NAME" \
  --attributes "RedrivePolicy=$REDRIVE_POLICY,VisibilityTimeout=900,MessageRetentionPeriod=1209600" \
  --query QueueUrl --output text)

QUEUE_ARN=$(aws sqs get-queue-attributes \
  --queue-url "$QUEUE_URL" --attribute-names QueueArn \
  --query 'Attributes.QueueArn' --output text)

echo "Created/using main queue $QUEUE_URL ($QUEUE_ARN)"

# Configure S3 → SQS event notifications (ObjectCreated in incoming/ *.pdf)
cat > /tmp/notification.json <<JSON
{
  "QueueConfigurations": [
    {
      "Id": "pdf-create-event",
      "QueueArn": "${QUEUE_ARN}",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [
            {"Name": "prefix", "Value": "incoming/"},
            {"Name": "suffix", "Value": ".pdf"}
          ]
        }
      }
    }
  ]
}
JSON

aws s3api put-bucket-notification-configuration \
  --bucket "$BUCKET_NAME" \
  --notification-configuration file:///tmp/notification.json

echo "✅ Infrastructure setup complete" 