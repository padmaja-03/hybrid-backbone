# Hybrid Backbone - Secure Data Orchestration Platform

## Overview
A multi-tenant platform for secure data ingestion and processing with full auditability. Member organizations upload sensitive data packages which are validated, processed by containerized workloads, and tracked through a complete audit trail.

## Architecture
![Hybrid Backbone Architecture](docs/architecture.png)

This diagram shows the event-driven workflow:
S3 → Lambda → ECS (Fargate) → DynamoDB audit trail.

## End-to-End Flow 
The system performs the following steps when a file is uploaded:

- File is uploaded to S3 ingress bucket with `organization-id` tag
- Lambda function is triggered automatically
- File metadata and organization-id are validated
- ECS Fargate task is started for processing
- Processor container:
  - Downloads file from S3 ingress bucket
  - Extracts organization metadata
  - Processes the file
  - Writes audit records to DynamoDB
- Audit trail captures all stages:
  - UPLOAD_DETECTED
  - VALIDATION_PASSED / FAILED
  - PROCESSING_STARTED
  - PROCESSING_COMPLETED / FAILED

For detailed execution steps, refer to [RUNBOOK.md]

- **Storage**: S3 bucket with KMS encryption, versioning, and strict bucket policies
- **Trigger**: Lambda function on S3 events with validation logic
- **Compute**: ECS Fargate tasks for isolated containerized processing
- **Audit**: DynamoDB with global secondary indexes for queryable event history
- **Security**: Least-privilege IAM roles, VPC endpoints, encryption at rest, TLS enforcement

## Prerequisites
- Terraform >= 1.0
- AWS CLI configured with appropriate credentials
- Docker (for building the processor container)
- Python 3.11 (for local testing)
