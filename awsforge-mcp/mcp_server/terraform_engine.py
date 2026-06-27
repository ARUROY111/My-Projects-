import os
import subprocess
import json
import shutil
import hashlib
from typing import Generator
from config import settings
from state_db import log_audit, save_resources

def _get_workspace_path(session_id: str) -> str:
    return os.path.abspath(os.path.join(settings.WORKSPACE_BASE_DIR, session_id))

def _run_cmd(cmd: list, cwd: str, timeout: int = settings.TF_APPLY_TIMEOUT_SECONDS) -> Generator[str, None, int]:
    env = os.environ.copy()
    env["TF_IN_AUTOMATION"] = "true"
    env["TF_CLI_ARGS_apply"] = "-compact-warnings"
    env["AWS_REGION"] = settings.AWS_REGION

    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env
    )
    
    try:
        for line in iter(process.stdout.readline, ''):
            yield line
        process.stdout.close()
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        yield "ERROR: Process timed out.\n"
        return 1
    
    return process.returncode

def init_workspace(session_id: str) -> dict:
    path = _get_workspace_path(session_id)
    os.makedirs(path, mode=0o700, exist_ok=True)
    
    cmd = [settings.TERRAFORM_BIN, "init", "-input=false"]
    result = subprocess.run(cmd, cwd=path, capture_output=True, text=True)
    return {"success": result.returncode == 0, "output": result.stdout + result.stderr}

def write_tf_files(session_id: str, hcl: str) -> None:
    path = _get_workspace_path(session_id)
    os.makedirs(path, mode=0o700, exist_ok=True)
    with open(os.path.join(path, "main.tf"), "w") as f:
        f.write(hcl)

def run_validate(session_id: str) -> dict:
    path = _get_workspace_path(session_id)
    cmd = [settings.TERRAFORM_BIN, "validate", "-json"]
    result = subprocess.run(cmd, cwd=path, capture_output=True, text=True)
    try:
        parsed = json.loads(result.stdout)
        return {"valid": parsed.get("valid", False), "errors": parsed.get("diagnostics", [])}
    except json.JSONDecodeError:
        return {"valid": False, "errors": [{"summary": "Failed to parse validation output", "detail": result.stderr}]}

def run_plan(session_id: str) -> Generator[str, None, None]:
    path = _get_workspace_path(session_id)
    cmd = [settings.TERRAFORM_BIN, "plan", "-input=false", "-no-color", "-out=tfplan"]
    yield from _run_cmd(cmd, cwd=path)

def run_apply(session_id: str) -> Generator[str, None, None]:
    path = _get_workspace_path(session_id)
    cmd = [settings.TERRAFORM_BIN, "apply", "-auto-approve", "-no-color", "-input=false", "tfplan"]
    
    hcl_hash = ""
    if os.path.exists(os.path.join(path, "main.tf")):
        with open(os.path.join(path, "main.tf"), "rb") as f:
            hcl_hash = hashlib.sha256(f.read()).hexdigest()

    exit_code = 0
    generator = _run_cmd(cmd, cwd=path)
    while True:
        try:
            line = next(generator)
            yield line
        except StopIteration as e:
            exit_code = e.value
            break
            
    log_audit(session_id, "apply", hcl_hash, exit_code)
    
    if exit_code == 0:
        outputs = get_outputs(session_id)
        save_resources(session_id, outputs)

def run_destroy(session_id: str) -> Generator[str, None, None]:
    path = _get_workspace_path(session_id)
    cmd = [settings.TERRAFORM_BIN, "destroy", "-auto-approve", "-no-color", "-input=false"]
    
    exit_code = 0
    generator = _run_cmd(cmd, cwd=path)
    while True:
        try:
            line = next(generator)
            yield line
        except StopIteration as e:
            exit_code = e.value
            break
            
    log_audit(session_id, "destroy", None, exit_code)
    if exit_code == 0:
        cleanup_workspace(session_id)

def get_outputs(session_id: str) -> dict:
    path = _get_workspace_path(session_id)
    cmd = [settings.TERRAFORM_BIN, "output", "-json"]
    result = subprocess.run(cmd, cwd=path, capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.strip():
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            pass
    return {}

def cleanup_workspace(session_id: str) -> None:
    path = _get_workspace_path(session_id)
    if os.path.exists(path):
        shutil.rmtree(path)

def run_nuke(force: bool = False) -> Generator[str, None, None]:
    cmd = ["/opt/awsforge/nuke.sh"]
    if force:
        cmd.append("--force")
    
    generator = _run_cmd(cmd, cwd="/opt/awsforge")
    exit_code = 0
    while True:
        try:
            line = next(generator)
            yield line
        except StopIteration as e:
            exit_code = e.value
            break
    log_audit("system", "nuke", None, exit_code)
