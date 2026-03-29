import logging
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import httpx

from config import AGENT_URL

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI()


class ChatRequest(BaseModel):
    text: str


class ChatResponse(BaseModel):
    response: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{AGENT_URL}/chat",
                json={"text": req.text},
            )
            r.raise_for_status()
            data = r.json()
            return ChatResponse(response=data.get("response", ""))
    except httpx.ConnectError:
        logger.error("Agent unreachable at %s", AGENT_URL)
        return ChatResponse(
            response="Sorry, I can't reach the agent right now. Please try again later."
        )
    except httpx.HTTPStatusError as e:
        logger.error("Agent returned error: %s", e)
        return ChatResponse(
            response="The agent encountered an error. Please try again."
        )
    except Exception as e:
        logger.error("Unexpected error contacting agent: %s", e)
        return ChatResponse(
            response="Something went wrong. Please try again later."
        )


# Serve main.js with no-cache so updates are picked up immediately
@app.get("/static/main.js")
async def get_main_js():
    headers = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
    return FileResponse(STATIC_DIR / "main.js", media_type="application/javascript", headers=headers)


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    from config import PORT

    uvicorn.run(app, host="0.0.0.0", port=PORT)
