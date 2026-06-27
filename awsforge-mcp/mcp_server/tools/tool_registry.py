# If connecting directly via standard MCP Clients (like Claude Desktop), 
# these tools expose the infrastructure engine over stdio/sse.

from mcp.server.fastmcp import FastMCP
from planner import generate_plan
from terraform_engine import init_workspace, write_tf_files

mcp = FastMCP("AWSForge")

@mcp.tool()
async def provision_aws_infrastructure(request_text: str, session_id: str) -> str:
    """
    Translates a natural language request into AWS infrastructure via Terraform.
    Does not apply immediately; it stages the plan for user approval.
    """
    plan_data = await generate_plan(request_text, [])
    if not plan_data["hcl"]:
        return "Failed to generate infrastructure code."
        
    init_workspace(session_id)
    write_tf_files(session_id, plan_data["hcl"])
    
    return f"Prepared plan for session {session_id}. HCL generated and staged. Awaiting explicit user /confirm."

@mcp.tool()
async def nuke_all_resources(confirmation: str) -> str:
    """
    Nuclear option to destroy all resources. confirmation MUST be 'DESTROY'.
    """
    if confirmation != "DESTROY":
        return "Nuke aborted. Confirmation string must be exactly 'DESTROY'."
    return "Nuke sequence initiated. Trigger the /nuke endpoint to stream output."
