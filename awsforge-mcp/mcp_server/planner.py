import os
from jinja2 import Environment, FileSystemLoader
import httpx
from anthropic import Anthropic
from config import settings

jinja_env = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), '..', 'terraform_templates')))

SYSTEM_PROMPT = """
You are an expert AWS Solutions Architect and Terraform Engineer.
Your task is to translate natural language requests into valid Terraform HCL.
CRITICAL RULES:
1. ONLY output valid Terraform HCL. Do not include markdown formatting or explanations in the HCL block.
2. Provider block must strictly be:
terraform { required_providers { aws = { source = "hashicorp/aws" version = "~> 5.0" } } }
provider "aws" { region = "ap-south-1" }
3. TAGGING IS MANDATORY. EVERY single AWS resource block MUST include this exact tags block:
  tags = {
    Project     = "AWSForgePOC"
    Environment = "POC"
    ManagedBy   = "AWSForge"
    CreatedBy   = "AWSForgeMCP"
  }
  The 'ManagedBy = "AWSForge"' tag is the security contract for the kill switch. Do not omit it.
4. Use random_id resources to generate unique suffixes for S3 buckets and IAM roles to prevent collisions.
5. Create necessary IAM roles and policies alongside resources (e.g., Lambda execution role).
6. Never use '*' in IAM actions or resources unless absolutely necessary. Scope down.
7. Use best practices for cost optimization (e.g., Serverless endpoints).
"""

def get_template_snippets() -> str:
    snippets = []
    for template_name in jinja_env.list_templates():
        if template_name.endswith('.tf.j2'):
            template = jinja_env.get_template(template_name)
            snippets.append(f"--- Example: {template_name} ---\n{template.render()}")
    return "\n\n".join(snippets)

async def call_llm(prompt: str) -> str:
    if settings.LLM_BACKEND == "anthropic":
        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    else:
        # Ollama local fallback
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_HOST}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "system": SYSTEM_PROMPT,
                    "prompt": prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            return response.json().get("response", "")

def extract_hcl(llm_output: str) -> str:
    # If the LLM wraps in markdown code blocks, extract it
    if "```hcl" in llm_output:
        parts = llm_output.split("```hcl")
        if len(parts) > 1:
            return parts[1].split("```")[0].strip()
    elif "```" in llm_output:
        parts = llm_output.split("```")
        if len(parts) > 1:
            return parts[1].strip()
    return llm_output.strip()

def validate_tags(hcl: str) -> bool:
    # Basic textual validation to ensure the critical tag exists.
    # A true robust solution would parse the HCL AST, but for POC, textual check is decent.
    return 'ManagedBy   = "AWSForge"' in hcl or 'ManagedBy="AWSForge"' in hcl

async def generate_plan(message: str, history: list) -> dict:
    if "mwaa" in message.lower() and "mwaa-confirm" not in message.lower():
        return {
            "hcl": "",
            "summary": "MWAA requested but blocked.",
            "warnings": ["⚠️ MWAA minimum cost is ~$300/month. Please explicitly type 'MWAA-CONFIRM' in your prompt to proceed."],
            "estimated_cost": "$300.00/mo+"
        }

    templates = get_template_snippets()
    
    full_prompt = f"""
Here are some verified Terraform templates for context. Use these patterns:
{templates}

Conversation History:
{history}

User Request: {message}

Generate the exact Terraform HCL to satisfy this request.
Respond ONLY with the HCL code.
"""
    raw_response = await call_llm(full_prompt)
    hcl = extract_hcl(raw_response)
    
    warnings = []
    if not validate_tags(hcl):
        warnings.append("⚠️ HCL generated without 'ManagedBy=AWSForge' tag. Regenerating...")
        # Simple one-pass retry
        full_prompt += "\n\nCRITICAL ERROR: Your previous response missed the ManagedBy tag. YOU MUST INCLUDE IT."
        raw_response = await call_llm(full_prompt)
        hcl = extract_hcl(raw_response)
        if not validate_tags(hcl):
            raise Exception("LLM repeatedly failed to include mandatory tags.")

    # Cost estimation heuristic for POC
    cost = "Free Tier / Negligible"
    if "aws_redshiftserverless" in hcl:
        cost = "~$25/mo base + compute"
    elif "aws_glue_job" in hcl:
        cost = "$0.44 per DPU-Hour"
    elif "mwaa" in hcl.lower():
        cost = "~$300/mo minimum"

    return {
        "hcl": hcl,
        "summary": f"Generated infrastructure for: {message[:50]}...",
        "warnings": warnings,
        "estimated_cost": cost
    }
