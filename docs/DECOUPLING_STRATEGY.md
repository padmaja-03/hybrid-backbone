# Storage-Compute Decoupling Strategy

## Current Architecture

The Hybrid Backbone decouples storage and compute through **event-driven orchestration**:

```
S3 Upload → Lambda Event → ECS Task (Processor)
            ↓              ↓
        Environment    Configuration
        Variables      Injection
```

**Key Components:**
- **Storage Layer**: S3 (ingress) + DynamoDB (audit)
- **Compute Layer**: Lambda (trigger) + ECS Fargate (processor)
- **Decoupling Mechanism**: Event notifications + environment-based configuration

## Decoupling Principles

1. **Configuration Over Hardcoding**: Storage/compute endpoints are environment variables
2. **S3-Compatible API**: Uses standard S3 SDK (works with S3-compatible services)
3. **IAM-Based Authentication**: Credentials managed via IAM roles, not embedded
4. **Stateless Processors**: ECS tasks are ephemeral and container-native

## Local Organization Deployment

Organizations can run on-premises **without Backbone rewrite** by:

### 1. **Local Storage (S3-Compatible)**
- Deploy MinIO, Wasabi, or on-prem S3-compatible service
- Processor uses existing S3 SDK → works seamlessly
- Update env var: `INGRESS_BUCKET=https://minio.org.local:9000/data`

### 2. **Local Compute (Self-Managed)**
- Pull processor container image (`hybrid-processor:latest`)
- Deploy on Kubernetes, Docker Swarm, or bare VM
- Update env vars:
  - `INGRESS_BUCKET` → local S3 endpoint
  - `AUDIT_TABLE_NAME` → local DynamoDB-compatible (DynamoDB Local, etc.)
  - IAM credentials → local service account

### 3. **Local Event Trigger (Instead of S3 Events)**
- Replace Lambda with:
  - **Kubernetes CronJob** (polling)
  - **Webhook listener** (on-prem CI/CD integration)
  - **Message queue subscriber** (RabbitMQ, Kafka)
- Webhook calls existing processor logic unchanged

### 4. **Audit Trail (Local DynamoDB)**
- Deploy DynamoDB Local or PlanetScale (DynamoDB-compatible)
- Use same table schema (PK, SK, GSI on OrganizationId)
- Processor DynamoDB calls work without modification

## Migration Path Example

```
Cloud Setup                          → Local Setup
─────────────────────────────────────────────────────
S3 (AWS)                            → MinIO (on-prem)
DynamoDB (AWS)                      → DynamoDB Local
Lambda + S3 Events                  → Kubernetes CronJob
ECS Fargate (container runtime)     → Docker/K8s (same container)
```

**Environment Changes Only:**
```bash
# Cloud
export INGRESS_BUCKET="hybrid-backbone-ingress-xxx"
export AUDIT_TABLE_NAME="hybrid-backbone-audit"
export AWS_REGION="eu-central-1"

# Local
export INGRESS_BUCKET="http://minio.local:9000/ingress"
export AUDIT_TABLE_NAME="local-audit"
export AWS_REGION="local"  # or omitted
export AWS_ENDPOINT_URL_S3="http://minio.local:9000"
export AWS_ENDPOINT_URL_DYNAMODB="http://localhost:8000"
```

## Why No Rewrite Needed

✅ **Processor logic is storage/compute agnostic** – uses standard SDKs  
✅ **Configuration injection via environment** – no code changes required  
✅ **Container-native design** – portable across cloud/on-prem  
✅ **S3 API compatibility** – works with any S3-compatible service  
✅ **Stateless architecture** – scales independently on-prem  

## Constraints & Considerations

- **Event notification** requires custom implementation (no S3 events locally)
- **Audit trail schema** must match DynamoDB-compatible service
- **IAM/authentication** needs local equivalent (service accounts, API keys)
- **Network security** (TLS, VPN) must be configured separately
- **Monitoring/logging** requires local CloudWatch alternative (ELK, Prometheus)

