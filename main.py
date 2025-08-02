from fastapi import FastAPI, UploadFile, File
from pathlib import Path
import subprocess, os, shutil, tempfile
import shlex

app = FastAPI()

BASE_PATH = Path.home() / "quantos" / "repos" / "quantos-core"   # agents can touch only this subtree

def _safe(path: Path) -> Path:
    p = path.resolve()
    if BASE_PATH not in p.parents and p != BASE_PATH:
        raise ValueError("path outside SAFE zone")
    return p

@app.get("/ping")
def ping(): return {"pong": "ok"}

@app.post("/fs_read")
def fs_read(rel_path: str):
    p = _safe(BASE_PATH / rel_path)
    return {"content": p.read_text()}

@app.post("/fs_write")
def fs_write(rel_path: str, content: str):
    p = _safe(BASE_PATH / rel_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return {"status": "written", "bytes": len(content)}

@app.post("/bash_cmd")
def bash_cmd(cmd: str):
    with tempfile.TemporaryDirectory() as d:
        res = subprocess.run(cmd, cwd=d, shell=True,
                             capture_output=True, text=True, timeout=30)
    return {"code": res.returncode, "stdout": res.stdout, "stderr": res.stderr}

@app.get("/health")
def health():
    """Light-weight liveness probe for orchestration tests."""
    return {"status": "alive"}

ALLOWED_GIT = {"status", "add", "commit", "push", "pull", "log", "diff"}

@app.get("/echo")
def echo(msg: str):
    return {"echo": msg}

@app.post("/git")
def git_cmd(rel_repo: str, sub_cmd: str):
    """
    rel_repo : path like 'quantos-core'
    sub_cmd  : one of the allowed git sub-commands plus its args
    """
    # safety checks
    repo_path = _safe(BASE_PATH / rel_repo)
    parts = shlex.split(sub_cmd)
    if not parts or parts[0] not in ALLOWED_GIT:
        return {"error": f"git sub-command not allowed: {parts[:1]}"}

    res = subprocess.run(
        ["git", *parts],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return {
        "code": res.returncode,
        "stdout": res.stdout[-4000:],  # trim huge logs
        "stderr": res.stderr[-4000:],
    }
