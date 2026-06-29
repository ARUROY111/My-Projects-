Technical Documentation: Self-Healing Data Pipeline

1. Overview

This system is an event-driven, serverless data pipeline hosted on AWS. It is designed to automatically ingest data from Amazon S3, process it, store it in DynamoDB, and intelligently handle errors via a "self-healing" mechanism that leverages automated retries and isolated quarantine zones.

2. Architecture Components

Ingestion: Amazon S3 (inbound/ prefix).

Orchestrator: AWS Step Functions (Standard Workflow).

Processing Logic: AWS Lambda (Python 3.12).

Storage (Success): Amazon DynamoDB (ProcessedData table).

Error Handling (DLQ): Amazon SQS (pipeline-dlq).

Event Routing: Amazon EventBridge.

3. Workflow Logic

3.1. Success Path (Happy Path)

Trigger: A file is uploaded to S3://[bucket]/inbound/. EventBridge detects the Object Created event.

Orchestration: Step Functions triggers the DataProcessorFunction.

Processing: The Lambda reads the JSON content, validates the schema (ensuring an id field exists), and writes the item to DynamoDB.

Completion: Step Functions marks the execution as successful.

3.2. Error Handling & Self-Healing

The system distinguishes between Transient and Poison Pill errors:

Transient Errors: (e.g., Network timeouts). The Step Function Retry block intercepts these exceptions and triggers an exponential backoff (3s interval, 2x backoff rate) for up to 2 attempts before failing.

Poison Pill Errors: (e.g., Invalid JSON, missing id field). These trigger an InvalidDataException. The Step Function Catch block immediately routes these to the QuarantineFunction.

3.3. Quarantine Procedure

The QuarantineFunction performs the following actions:

Isolation: Copies the offending file from inbound/ to quarantine/ in the S3 bucket.

Cleanup: Deletes the file from inbound/.

Notification: Sends a metadata payload (bucket, key, error type) to the SQS queue for manual engineer review.

4. Configuration & Deployment Summary

Runtime: Python 3.12

IAM Policies: * LambdaProcessor: S3 Read + DynamoDB Write.

LambdaQuarantine: S3 Read/Write/Delete + SQS SendMessage.

StepFunctions: Lambda Invoke access.

Environment Variables: * QuarantineFunction requires SQS_QUEUE_URL to route alerts.

5. Maintenance & Observability

CloudWatch Logs: All Lambda functions send logs to CloudWatch. Use the Step Function Execution ARN to trace failures.

Monitoring: Monitor the pipeline-dlq SQS queue. A non-zero message count indicates files have been quarantined and require manual investigation.

Retries: Review Step Function metrics to optimize IntervalSeconds and MaxAttempts based on observed network instability.
