"""Layer 2 bridge — HTTP API backed by a persistent opencode serve instance.

Starts `opencode serve` on init, then each request uses
`opencode run --attach` to talk to the warm server.
Session continuity via --continue.
"""
import asyncio
import json
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

OPENCODE_BIN = os.getenv("OPENCODE_BIN", "opencode")
OPENCODE_PORT = int(os.getenv("OPENCODE_PORT", "4096"))
OPENCODE_URL = f"http://127.0.0.1:{OPENCODE_PORT}"
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))

_serve_process: asyncio.subprocess.Process | None = None


class ChatRequest(BaseModel):
    text: str


class ChatResponse(BaseModel):
    response: str


async def _start_opencode_serve():
    """Start opencode serve as a managed background process."""
    global _serve_process
    if _serve_process and _serve_process.returncode is None:
        return  # already running

    logger.info("Starting opencode serve on port %d ...", OPENCODE_PORT)
    _serve_process = await asyncio.create_subprocess_exec(
        OPENCODE_BIN, "serve",
        "--port", str(OPENCODE_PORT),
        "--hostname", "127.0.0.1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=WORKSPACE_DIR,
    )

    # Wait for it to be ready (poll health or just give it a moment)
    await asyncio.sleep(2)
    logger.info("opencode serve started (pid=%d)", _serve_process.pid)


async def _ensure_serve_running():
    """Ensure the opencode serve process is alive, restart if needed."""
    global _serve_process
    if _serve_process is None or _serve_process.returncode is not None:
        await _start_opencode_serve()


@app.on_event("startup")
async def on_startup():
    await _start_opencode_serve()


@app.on_event("shutdown")
async def on_shutdown():
    global _serve_process
    if _serve_process and _serve_process.returncode is None:
        logger.info("Shutting down opencode serve ...")
        _serve_process.terminate()
        try:
            await asyncio.wait_for(_serve_process.wait(), timeout=5)
        except asyncio.TimeoutError:
            _serve_process.kill()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send text to the persistent opencode server, return response."""
    await _ensure_serve_running()

    try:
        cmd = [
            OPENCODE_BIN, "run",
            request.text,
            "--attach", OPENCODE_URL,
            "--continue",
            "--format", "json",
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=WORKSPACE_DIR,
        )

        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)

        if process.returncode != 0:
            logger.error("opencode run error (rc=%d): %s", process.returncode, stderr.decode()[:500])
            return ChatResponse(response="Sorry, I had trouble processing that. Please try again.")

        output = stdout.decode().strip()

        # Parse NDJSON — collect all text parts
        text_parts = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get("type") == "text":
                    text_parts.append(obj.get("part", {}).get("text", ""))
            except json.JSONDecodeError:
                continue

        response_text = "\n".join(text_parts).strip() if text_parts else output
        return ChatResponse(response=response_text)

    except asyncio.TimeoutError:
        logger.error("opencode run timed out after 120s")
        return ChatResponse(response="Request timed out. Please try again.")
    except FileNotFoundError:
        logger.error("OpenCode binary not found at: %s", OPENCODE_BIN)
        return ChatResponse(response="Agent is not configured yet. Please install OpenCode.")
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        return ChatResponse(response="An unexpected error occurred.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)
