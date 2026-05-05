# Hybrid Backbone - Secure Data Orchestration Platform

## Overview
A multi-tenant platform for secure data ingestion and processing with full auditability. Member organizations upload sensitive data packages which are validated, processed by containerized workloads, and tracked through a complete audit trail.

## Architecture
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

## Deployment

### 1. Build and Push Processor Container
```bash
# Build the Docker image
cd src/processor
docker build -t hybrid-processor .

# Authenticate to ECR (after Terraform deploy - get repo URL from outputs)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Tag and push
docker tag hybrid-processor:latest <ecr-repo-url>:latest
docker push <ecr-repo-url>:latest