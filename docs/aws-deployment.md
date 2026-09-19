# AWS Deployment Guide

## Prerequisites

- AWS account with Bedrock model access enabled
- AWS CLI v2 installed and configured
- Docker installed
- Python 3.11+, Node.js 20+

### Required AWS Services

- Amazon Bedrock (Claude model access)
- Amazon ECS (Fargate) or EC2 for backend hosting
- Amazon ECR for container images
- Amazon S3 + CloudFront (or Vercel/Amplify) for frontend
- Amazon CloudWatch (logs and alarms)
- AWS X-Ray (optional, for distributed tracing)
- Amazon Bedrock AgentCore (optional, for persistent memory)

## IAM Configuration

Create a dedicated IAM role for the backend service. Do not use AdministratorAccess.

### Minimum Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockInvoke",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:*::foundation-model/*"
    },
    {
      "Sid": "CloudWatchRead",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:DescribeAlarms",
        "cloudwatch:GetMetricData",
        "logs:FilterLogEvents",
        "logs:GetLogEvents"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ECSOperations",
      "Effect": "Allow",
      "Action": [
        "ecs:DescribeServices",
        "ecs:UpdateService",
        "ecs:DescribeTasks",
        "ecs:ListTasks"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AutoScaling",
      "Effect": "Allow",
      "Action": [
        "application-autoscaling:RegisterScalableTarget",
        "application-autoscaling:PutScalingPolicy"
      ],
      "Resource": "*"
    },
    {
      "Sid": "XRayWrite",
      "Effect": "Allow",
      "Action": [
        "xray:PutTraceSegments",
        "xray:PutTelemetryRecords"
      ],
      "Resource": "*"
    }
  ]
}
```

If using AgentCore Memory, add the appropriate `bedrock-agentcore:*` permissions for your memory resource.

## Environment Variables

Set these on your ECS task definition or EC2 instance:

```bash
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514
AGENTCORE_MEMORY_ID=your-memory-id
SIMULATION_MODE=false
OTEL_ENABLED=true
OTEL_EXPORTER_ENDPOINT=http://otel-collector:4317
```

## Deployment Steps

### 1. Build and Push Backend Image

```bash
# Create ECR repository
aws ecr create-repository --repository-name autonomous-sre-backend

# Login to ECR
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com

# Build and push
cd backend
docker build -t autonomous-sre-backend .
docker tag autonomous-sre-backend:latest <account>.dkr.ecr.<region>.amazonaws.com/autonomous-sre-backend:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/autonomous-sre-backend:latest
```

### 2. Deploy Backend on ECS Fargate

Create an ECS cluster, task definition, and service:

- **Cluster**: `autonomous-sre`
- **Task Definition**: Use the ECR image, 1 vCPU, 2GB memory, port 8000
- **Service**: Desired count 1, Fargate launch type
- **Load Balancer**: ALB with target group pointing to port 8000
- **Task Role**: Attach the IAM policy above

### 3. Deploy Frontend

**Option A: Vercel (recommended for demos)**
```bash
cd frontend
npx vercel --prod
```
Set `NEXT_PUBLIC_API_URL` to your backend ALB URL.

**Option B: S3 + CloudFront**
```bash
cd frontend
npm run build
aws s3 sync out/ s3://your-bucket/
```

**Option C: ECS (same cluster)**
Build and push the frontend Docker image similarly.

### 4. Configure CloudWatch

If monitoring real services, ensure the target ECS services have CloudWatch Container Insights enabled and log groups configured. The backend tools query:
- Log group: `/ecs/{service-name}`
- Alarms: filtered by service name prefix

### 5. Configure X-Ray

Deploy an OpenTelemetry Collector as a sidecar or standalone service, configured to export to X-Ray:

```yaml
exporters:
  awsxray:
    region: us-east-1
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [awsxray]
```

Set `OTEL_EXPORTER_ENDPOINT` to point to this collector.

## SageMaker Integration

See [SageMaker section below](#sagemaker) for when and how SageMaker fits into this architecture.

<a id="sagemaker"></a>
### When SageMaker is Useful

SageMaker is **not required** to deploy this application. The Strands Agents SDK uses Amazon Bedrock directly for LLM inference.

SageMaker becomes relevant when:

1. **Monitoring SageMaker endpoints**: The SRE agents can monitor SageMaker inference endpoints the same way they monitor ECS services. Add CloudWatch alarms for `InvocationErrors`, `ModelLatency`, and `Invocations` metrics on the `aws/sagemaker` namespace.

2. **Custom anomaly detection models**: You could train and deploy custom anomaly detection models on SageMaker and have the Log Analyst query them for predictions instead of relying solely on threshold-based detection.

3. **SageMaker endpoint remediation**: The Remediator can interact with SageMaker endpoints by adding actions to the allowlist (e.g., `update_endpoint_config` to change instance type or count).

SageMaker is **unnecessary** for:
- Running the Strands agents (use Bedrock)
- Hosting the FastAPI backend (use ECS/EC2)
- Serving the frontend (use S3/CloudFront/Vercel)

## Verification

After deployment:

```bash
# Health check
curl https://your-alb-url/health

# Trigger simulation
curl -X POST https://your-alb-url/api/simulate

# Open dashboard
open https://your-frontend-url
```
