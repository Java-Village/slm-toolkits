"""
main.py
-------
FastAPI application that proxies /v1/chat/completions
to the LLM endpoint specified in configure.json
"""

import time
import uuid
from typing import List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .settings import get_settings

settings = get_settings()
app = FastAPI(title="Local-LM Proxy", version="1.0.0")


# ------------------------------------------------------------------ #
# Data models
# ------------------------------------------------------------------ #
class ChatMessage(BaseModel):
    role: str = Field(..., regex="^(system|user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    stream: Optional[bool] = None


# ------------------------------------------------------------------ #
# Helper functions
# ------------------------------------------------------------------ #
def build_headers() -> dict:
    """
    Construct HTTP headers depending on provider type.
    Local models require only Content-Type.
    """
    if settings.provider in {"openai", "grok"}:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.api_key}",
        }
    return {"Content-Type": "application/json"}


def build_payload(body: ChatRequest) -> dict:
    """
    Merge client request with default options defined in configuration.
    Explicit fields in body take precedence.
    """
    payload = {
        "model": body.model or settings.model,
        "messages": [m.dict() for m in body.messages],
        **settings.request_opts,
    }
    if body.stream is not None:
        payload["stream"] = body.stream
    return payload

# ------------------------------------------------------------------ #
# App Solar Task
# ------------------------------------------------------------------ #
@app.post("/v1/chat/solar-task")
async def solar_prompted_chat(req: ChatRequest):
    system_prompt = settings.prompts.get("drone-task", settings.prompts["default"])
    req.messages.insert(0, ChatMessage(role="system", content=system_prompt))
    return await proxy_chat(req)


# ------------------------------------------------------------------ #
# Routes
# ------------------------------------------------------------------ #
@app.post("/v1/chat/completions")
async def proxy_chat(req: ChatRequest):
    start = time.time()
    payload = build_payload(req)
    headers = build_headers()

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(settings.lm_api_url, json=payload, headers=headers)

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code,
                            detail=f"Upstream error: {resp.text}")

    result = resp.json()
    result["proxy_request_id"] = str(uuid.uuid4())
    result["latency_ms"] = round((time.time() - start) * 1000, 1)
    return result
