# ⚡ AWSForge MCP v2

AWSForge is an open-source, self-hosted Model Context Protocol (MCP) server running on AWS EC2. It allows users to provision and manage AWS infrastructure through natural language via a chat UI, using **Terraform** as the sole infrastructure provisioning engine.

## 🎯 Features
* **Natural Language to Infrastructure:** Chat with an LLM to generate Terraform HCL.
* **Non-Bypassable Confirmation Gate:** Review `terraform plan` output before anything is built.
* **Cost Guardrails:** Auto-deploys an AWS Budget alert ($30/$48/$60) on setup.
* **Nuclear Kill Switch:** A `nuke.sh` script that destroys all workspaces and sweeps AWS for orphaned resources via tag (`ManagedBy=AWSForge`).
* **Zero API Cost Option:** Run locally via Ollama (`mistral`) on the EC2 instance, or plug in Anthropic Claude via `.env`.

---

## 🚀 A→Z Deployment Guide

### Phase 1: AWS Setup
1. **Create an IAM Role** for EC2 and attach these managed policies:
   * `AmazonS3FullAccess`, `AWSGlueConsoleFullAccess`, `AmazonAthenaFullAccess`
   * `AmazonRedshiftFullAccess`, `AmazonSNSFullAccess`, `AmazonSQSFullAccess`
   * `AWSLambda_FullAccess`, `AmazonEventBridgeFullAccess`, `IAMFullAccess`
   * `AmazonMWAAFullConsoleAccess`, `AWSBudgetsActionsWithAWSResourceControlPolicy`
2. **Launch an EC2 Instance**:
   * **OS:** Ubuntu 22.04 LTS
   * **Type:** `t3.medium` (Minimum requirement for local LLM + Terraform)
   * **Storage:** 20GB gp3
   * **Security Group:** Inbound 22 (SSH from your IP), Inbound 80 (HTTP 0.0.0.0/0)
   * **IAM:** Attach the role created in Step 1.

### Phase 2: Server Installation
1. **SSH into your instance:**
   ```bash
   ssh -i /path/to/key.pem ubuntu@<EC2-PUBLIC-IP>
