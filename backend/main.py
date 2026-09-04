"""Generative UI backend, speaking A2UI v0.9.

App assembly only: environment, logging, CORS, and the routers. POST a
free-text message to /api/generate and the response is a stream of A2UI
messages that `@a2ui/react` renders directly. Every turn re-composes ONE fixed
surface: the client deletes it, the stream re-creates the same id, and the
dashboard re-forms in place rather than stacking answer under answer.

The stream never raises to the client: a missing API key, an OpenAI error or a
schema violation all resolve to a `text_note` block, so the renderer is never
handed a surface it cannot draw.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Importing the api package pulls in agent.prompts, which renders the dataset
# into the system prompt once -- after load_dotenv so OPENAI_MODEL is honored.
from api import api_router  # noqa: E402

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

app = FastAPI(title="Generative UI — A2UI Financial Dashboard", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(api_router)
