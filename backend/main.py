"""Generative UI backend.

POST a free-text message, get back one validated dashboard component to render.
The endpoint never raises to the client: every failure path -- missing API key,
OpenAI error, schema violation -- resolves to a text_note so the frontend has a
single happy path and can never be handed a shape it does not understand.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import ValidationError

from mock_data import dashboard_payload, dataset_for_prompt
from schemas import (
    BarChart,
    Component,
    DataTable,
    DonutChart,
    GenerateRequest,
    GenerateResponse,
    LineChart,
    TextNote,
    UIDecision,
)

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("genui")

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

MAX_SERIES = 4
MAX_POINTS = 24
MAX_SLICES = 6
MAX_ROWS = 25
MAX_FOLLOW_UPS = 3
MAX_FOLLOW_UP_CHARS = 70

# Shown when the model never got far enough to suggest anything of its own.
DEFAULT_FOLLOW_UPS = [
    "Show revenue as a line chart",
    "Expenses by category as a bar chart",
    "What was net cash flow in August?",
]

SYSTEM_PROMPT = f"""You are the rendering engine for a financial dashboard. The user \
describes what they want to see; you choose exactly one UI component from the catalog \
and fill it with real numbers from the dataset below.

Rules:
- Use only numbers that appear in the dataset, or arithmetic derived from them \
(sums, differences, percentages, averages). Never invent figures.
- Pick the component that fits the question, not the one the user names, unless they \
name one explicitly. Trends over months are line charts. Comparisons across categories \
are bar charts. A single figure is a stat card. Composition of a whole is a donut, and \
only when the parts really do sum to that whole. Lists of records are tables.
- At most {MAX_SERIES} series per chart and at most {MAX_SLICES} donut slices; roll the \
tail into "Other".
- Sort categorical data largest first. Keep time series in chronological order.
- Table cells are pre-formatted strings: thousands separators, a leading "$" on money, \
a leading "-" for money out.
- When asked for the largest, smallest, top or biggest records, sort by the relevant \
measure across the WHOLE dataset before selecting, and return every row that qualifies \
(up to {MAX_ROWS}). Do not stop at the first few rows you happen to read.
- If the request is unrelated to this data or cannot be answered from it, return a \
text_note saying so plainly. Do not guess.
- Every component needs a short, specific title -- "Revenue by Month", not "A chart of \
the revenue" and never the literal word "Title". This applies to text_note too: title \
it with the subject, e.g. "Out of scope".
- Always return exactly three follow_ups: short requests the user could send next, \
phrased the way they would type them ("Compare against expenses", not "Would you like \
to compare against expenses?"). Each must be answerable from this dataset, must lead \
somewhere different from the other two, and must not restate the request you just \
answered. Under 60 characters each. If the request was out of scope, suggest three \
things this dashboard CAN answer.

DATASET
{dataset_for_prompt()}
"""

app = FastAPI(title="Generative UI — Financial Dashboard", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_client: OpenAI | None = None


def get_client() -> OpenAI:
    """Lazily build the OpenAI client so the app still boots without a key."""
    global _client
    if _client is None:
        _client = OpenAI()  # reads OPENAI_API_KEY from the environment
    return _client


def note(title: str, body: str) -> TextNote:
    return TextNote(type="text_note", title=title, body=body)


def clean_follow_ups(raw: list[str], asked: str) -> list[str]:
    """Trim, de-duplicate and drop anything that just echoes the request.

    Unlike the component, a bad follow-up is not worth failing the request
    over -- an empty list simply renders no chips.
    """
    seen: set[str] = {asked.strip().casefold()}
    cleaned: list[str] = []

    for item in raw:
        text = " ".join(item.split())
        key = text.casefold()
        if not text or len(text) > MAX_FOLLOW_UP_CHARS or key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
        if len(cleaned) == MAX_FOLLOW_UPS:
            break

    return cleaned


def sanitize(component: Component) -> Component:
    """Enforce the limits the prompt asks for but the schema cannot express.

    Structured outputs guarantee the shape, not the sense of it -- a model can
    still return nine series or a table row with the wrong number of cells. We
    trim what is trimmable and raise on what is not, so the caller can fall back.
    """
    if isinstance(component, (LineChart, BarChart)):
        component.series = component.series[:MAX_SERIES]
        if not component.series:
            raise ValueError("chart has no series")
        for series in component.series:
            series.points = series.points[:MAX_POINTS]
        if not any(series.points for series in component.series):
            raise ValueError("chart has no data points")

    elif isinstance(component, DonutChart):
        slices = [s for s in component.slices if s.value > 0][:MAX_SLICES]
        if len(slices) < 2:
            raise ValueError("donut needs at least two positive slices")
        component.slices = slices

    elif isinstance(component, DataTable):
        if not component.columns:
            raise ValueError("table has no columns")
        width = len(component.columns)
        # Drop malformed rows rather than shipping a ragged table.
        component.rows = [row for row in component.rows[:MAX_ROWS] if len(row) == width]
        if not component.rows:
            raise ValueError("table has no well-formed rows")

    return component


def ask_model(message: str) -> UIDecision:
    """One structured-output call. The response_format IS the component catalog."""
    client = get_client()
    completion = client.beta.chat.completions.parse(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        response_format=UIDecision,
        temperature=0.2,
    )
    choice = completion.choices[0]
    if choice.message.refusal:
        raise ValueError(f"model refused: {choice.message.refusal}")
    if choice.message.parsed is None:
        raise ValueError("model returned no parseable output")
    return choice.message.parsed


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "model": MODEL, "openai_key_set": bool(os.getenv("OPENAI_API_KEY"))}


@app.get("/api/dashboard")
def dashboard() -> dict:
    """The mock dataset the dashboard renders on load."""
    return dashboard_payload()


@app.post("/api/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest) -> GenerateResponse:
    """Turn a free-text request into one validated dashboard component."""
    if not os.getenv("OPENAI_API_KEY"):
        return GenerateResponse(
            ok=False,
            explanation="The server has no OpenAI API key configured.",
            component=note(
                "Missing API key",
                "Set OPENAI_API_KEY in the server's environment and restart it, then try again. "
                "Locally that is backend/.env; under Docker it is the .env next to compose.yaml.",
            ),
            follow_ups=DEFAULT_FOLLOW_UPS,
            fallback=True,
            error="OPENAI_API_KEY is not set",
        )

    try:
        decision = ask_model(request.message)
        component = sanitize(decision.component)
    except ValidationError as exc:
        logger.warning("model output failed validation: %s", exc)
        return GenerateResponse(
            ok=False,
            explanation="The model's response didn't match the component schema.",
            component=note(
                "Could not render that",
                "The model returned something outside the component catalog. "
                "Try rephrasing, for example: 'show revenue by month as a line chart'.",
            ),
            follow_ups=DEFAULT_FOLLOW_UPS,
            fallback=True,
            error="schema validation failed",
        )
    except ValueError as exc:
        logger.warning("unusable component: %s", exc)
        return GenerateResponse(
            ok=False,
            explanation="The model picked a component it couldn't fill with usable data.",
            component=note(
                "Could not render that",
                f"Nothing renderable came back ({exc}). Try rephrasing your request.",
            ),
            follow_ups=DEFAULT_FOLLOW_UPS,
            fallback=True,
            error=str(exc),
        )
    except Exception as exc:  # network, auth, rate limit, anything upstream
        logger.exception("generation failed")
        return GenerateResponse(
            ok=False,
            explanation="The request to the model failed.",
            component=note(
                "Something went wrong",
                f"{type(exc).__name__}: {exc}. Check the server logs and try again.",
            ),
            follow_ups=DEFAULT_FOLLOW_UPS,
            fallback=True,
            error=f"{type(exc).__name__}: {exc}",
        )

    return GenerateResponse(
        ok=True,
        explanation=decision.explanation,
        component=component,
        follow_ups=clean_follow_ups(decision.follow_ups, request.message),
    )
