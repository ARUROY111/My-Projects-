# ⚡ AWSForge MCP v2

AWSForge is an open-source, self-hosted Model Context Protocol (MCP) server deployed on a single AWS EC2 instance. It acts as an intelligent infrastructure-as-code (IaC) assistant, allowing users to provision, manage, and destroy AWS cloud resources using natural language via a web-based chat interface. 

The system uses **HashiCorp Terraform** as its exclusive execution engine and incorporates LLM reasoning (via Ollama or Anthropic) to translate user requests into valid Terraform HCL.

---

## 🎯 Target Audience & Use Case
This tool is intended for **Cloud Architects, DevOps Engineers, and Developers** who need a rapid, sandboxed environment for Proof of Concept (POC) infrastructure generation. It is designed to bridge the gap between architectural brainstorming and functional Terraform code, prioritizing speed, experimentation, and aggressive cleanup over enterprise-grade lifecycle management.

---

## ✨ Core Features & Capabilities

* **Natural Language to Infrastructure:** Chat with an LLM to automatically translate conversational prompts (e.g., "Build an S3 to Lambda pipeline") into syntactically correct Terraform configuration files (`main.tf`).
* **Dry-Run Validations:** Automatically runs `terraform validate` and `terraform plan` to preview infrastructure changes before any actual AWS resources are created.
* **Stateful Provisioning:** Executes `terraform apply -auto-approve` upon explicit user approval, tracking deployed resource ARNs in a local SQLite database.
* **Session Management:** Isolates different chats and deployments into unique workspace directories (`/opt/awsforge/workspaces/{session_id}/`).
* **Automated IAM Generation:** Intelligently drafts and attaches necessary IAM roles, trust policies, and least-privilege inline policies required to link requested services together.
* **Real-time Streaming:** Streams Terraform subprocess console outputs directly to the frontend UI via Server-Sent Events (SSE).
* **Zero API Cost Option:** Run locally via Ollama (`mistral`) on the EC2 instance, or plug in Anthropic Claude via the `.env` file.

---

## 📦 Supported AWS Resources
The LLM is currently scoped to confidently generate and link the following AWS resources using pre-approved Jinja2 templates:

* **Storage:** Amazon S3 (with versioning, encryption, and public access blocks).
* **Compute/Serverless:** AWS Lambda (Python 3.11 runtimes).
* **Data & Analytics:** AWS Glue (Jobs & Crawlers), Amazon Athena (Workgroups), Amazon Redshift Serverless (Namespaces & Workgroups).
* **Integration & Messaging:** Amazon SNS, Amazon SQS (with DLQ support), Amazon EventBridge (Schedules and Rules).
* **Orchestration:** Amazon MWAA (Managed Workflows for Apache Airflow) — *Restricted by default.*
* **Security:** AWS IAM (Roles, Policies, Attachments).

---

## 🛡️ Security & Cost Guardrails
AWSForge is built with strict boundaries to prevent runaway costs and unauthorized or dangerous deployments:

* **Non-Bypassable Confirmation Gate:** The system will *never* provision resources autonomously. Users must visually review the generated HCL and `terraform plan` output and explicitly click "Approve" before anything is built.
* **Automated Cost Alerts:** Upon installation, the bootstrap script automatically provisions an AWS Budget in `us-east-1` tracked against a hard $60 limit, sending emails at $30 (50%), $48 (80%), and $60 (100% forecasted).
* **Strict Tagging Contract:** Every single resource provisioned by AWSForge is forcefully tagged with `ManagedBy=AWSForge`. The LLM planner validates that this tag exists in the generated HCL before allowing a deployment.
* **Restricted Services (MWAA):** High-cost services like MWAA (~$300/mo minimum) are blocked by the planner unless the user types an explicit override code (`MWAA-CONFIRM`).
* **Two-Phase Nuclear Teardown:** The `nuke.sh` script provides a total kill-switch. Phase 1 iterates through all Terraform workspaces and runs `terraform destroy`. Phase 2 uses the AWS CLI to sweep the entire region for the `ManagedBy=AWSForge` tag to catch and forcefully delete any orphaned resources (like auto-generated CloudWatch log groups or S3 versions).

---

## 🚀 A→Z Deployment Guide

### Phase 1: AWS Setup
1. **Create an IAM Role** for EC2 and attach these managed policies:
   * `AmazonS3FullAccess`
   * `AWSGlueConsoleFullAccess`
   * `AmazonAthenaFullAccess`
   * `AmazonRedshiftFullAccess`
   * `AmazonSNSFullAccess`
   * `AmazonSQSFullAccess`
   * `AWSLambda_FullAccess`
   * `AmazonEventBridgeFullAccess`
   * `IAMFullAccess`
   * `AmazonMWAAFullConsoleAccess`
   * `AWSBudgetsActionsWithAWSResourceControlPolicy`
2. **Launch an EC2 Instance**:
   * **OS:** Ubuntu 22.04 LTS
   * **Type:** `t3.medium` *(Minimum requirement for local LLM + Terraform)*
   * **Storage:** 20GB gp3
   * **Security Group:** Inbound 22 (SSH from your IP only), Inbound 80 (HTTP 0.0.0.0/0)
   * **IAM:** Attach the role created in Step 1.

### Phase 2: Server Installation
1. **SSH into your instance:**
   ```bash
   ssh -i /path/to/key.pem ubuntu@<EC2-PUBLIC-IP>

