import os
import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Generator
import uuid

from config import settings
from state_db import get_session_status, get_all_resources, update_session_status
from planner import generate_plan
from terraform_engine import init_workspace, write_tf_files, run_plan, run_apply, run_destroy, run_nuke, cleanup_workspace

app = FastAPI(title="AWSForge MCP Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ConfirmRequest(BaseModel):
    session_id: str
    approved: bool

class DestroyRequest(BaseModel):
    session_id: str

class NukeRequest(BaseModel):
    confirm: str

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    ui_path = os.path.join(os.path.dirname(__file__), "..", "ui", "index.html")
    with open(ui_path, "r") as f:
        return f.read()

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    update_session_status(req.session_id, "planning")
    
    # Generate HCL via LLM Planner
    history = [] # In a production system, fetch from DB. For POC, passing empty context.
    plan_data = await generate_plan(req.message, history)
    
    if not plan_data["hcl"]:
        update_session_status(req.session_id, "failed")
        return plan_data

    # Terraform Init & Write
    init_workspace(req.session_id)
    write_tf_files(req.session_id, plan_data["hcl"])
    
    update_session_status(req.session_id, "awaiting_approval")
    return plan_data

@app.get("/plan/{session_id}")
async def stream_plan(session_id: str):
    def event_generator() -> Generator[str, None, None]:
        for line in run_plan(session_id):
            yield f"data: {line}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/confirm")
async def confirm_endpoint(req: ConfirmRequest):
    if not req.approved:
        cleanup_workspace(req.session_id)
        update_session_status(req.session_id, "rejected")
        return {"status": "workspace_cleaned"}

    update_session_status(req.session_id, "applying")
    return {"status": "starting_apply"}

@app.get("/apply/{session_id}")
async def stream_apply(session_id: str):
    def event_generator() -> Generator[str, None, None]:
        for line in run_apply(session_id):
            yield f"data: {line}\n\n"
        yield "data: [DONE]\n\n"
        update_session_status(session_id, "complete")
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/destroy")
async def destroy_endpoint(req: DestroyRequest):
    update_session_status(req.session_id, "destroying")
    return {"status": "starting_destroy"}

@app.get("/destroy/stream/{session_id}")
async def stream_destroy(session_id: str):
    def event_generator() -> Generator[str, None, None]:
        for line in run_destroy(session_id):
            yield f"data: {line}\n\n"
        yield "data: [DONE]\n\n"
        update_session_status(session_id, "destroyed")
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/nuke")
async def nuke_endpoint(req: NukeRequest):
    if req.confirm != "DESTROY":
        raise HTTPException(status_code=400, detail="Must explicitly confirm with 'DESTROY'")
    return {"status": "starting_nuke"}

@app.get("/nuke/stream")
async def stream_nuke():
    def event_generator() -> Generator[str, None, None]:
        for line in run_nuke(force=True):
            yield f"data: {line}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/status/{session_id}")
async def status_endpoint(session_id: str):
    return {"status": get_session_status(session_id)}

@app.get("/resources")
async def resources_endpoint():
    return {"resources": get_all_resources()}
