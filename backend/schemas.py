"""The component catalog, as the agent thinks about it.

These Pydantic models constrain what the LLM is allowed to emit: they become
the JSON Schema passed to OpenAI as `response_format`, and they validate the
result before anything is compiled to A2UI.

This is deliberately NOT the A2UI wire format. A2UI messages are a flat,
loosely-typed component stream -- excellent for renderers, hostile to
schema-constrained generation. So the agent plans in these typed blocks, and
`a2ui.py` compiles the plan into real A2UI v0.9 messages. The wire and the
client are genuine A2UI; only the agent's internal planning step is typed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Unit = Literal["USD", "%", "count", "none"]
Direction = Literal["up", "down", "flat"]
Align = Literal["left", "right"]


class Point(BaseModel):
    """One (category or time bucket, value) pair."""

    x: str = Field(description="Axis label, e.g. '2026-03' or 'Marketing'.")
    y: float = Field(description="The numeric value at x.")


class Series(BaseModel):
    name: str = Field(description="Series name shown in the legend, e.g. 'Revenue'.")
    points: list[Point] = Field(description="Points in display order, left to right.")


class Slice(BaseModel):
    label: str
    value: float = Field(description="Must be non-negative; shares of a whole.")


class Column(BaseModel):
    key: str = Field(description="Short identifier, e.g. 'amount'.")
    label: str = Field(description="Human-readable header, e.g. 'Amount (USD)'.")
    align: Align = Field(description="Use 'right' for numeric columns, 'left' otherwise.")


class BlockAction(BaseModel):
    """A button rendered inside a card that sends an action back to the agent.

    This is what makes the UI agentic rather than a picture: the label is what
    the user sees, the prompt is what the agent receives when it is clicked.
    """

    label: str = Field(description="Button text, 2-4 words, e.g. 'Split by region'.")
    prompt: str = Field(
        description=(
            "The request to send back when clicked, phrased as the user would type it. "
            "Must be answerable from the dataset and must change what is on screen."
        )
    )


class StatCard(BaseModel):
    """A single headline number. Use when the answer is one figure."""

    type: Literal["stat_card"]
    # `title` names the measure -- "Net Cash Flow (Q4)". There is deliberately
    # no separate label field: the title is the heading, and a second copy of
    # the same words underneath it is what the previous version rendered.
    title: str
    value: float
    unit: Unit
    delta_pct: float = Field(description="Percent change vs. the comparison period; 0 if unknown.")
    delta_direction: Direction
    caption: str = Field(description="Short context line, e.g. 'vs. prior 12 months'.")
    actions: list[BlockAction] = Field(description="Zero to two follow-on actions.")


class LineChart(BaseModel):
    """Change over time. Use for anything trending across months."""

    type: Literal["line_chart"]
    title: str
    x_label: str
    y_label: str
    unit: Unit
    series: list[Series] = Field(description="One to four series. More than four is unreadable.")
    actions: list[BlockAction] = Field(description="Zero to two follow-on actions.")


class BarChart(BaseModel):
    """Comparison across categories, or period-over-period totals."""

    type: Literal["bar_chart"]
    title: str
    x_label: str
    y_label: str
    unit: Unit
    stacked: bool = Field(description="True only when the series sum to a meaningful total.")
    series: list[Series] = Field(description="One to four series sharing the same x values.")
    actions: list[BlockAction] = Field(description="Zero to two follow-on actions.")


class DonutChart(BaseModel):
    """Composition of a whole. Only when parts genuinely sum to 100%."""

    type: Literal["donut_chart"]
    title: str
    unit: Unit
    slices: list[Slice] = Field(
        description="Two to six slices, largest first. Roll up the tail into 'Other'."
    )
    actions: list[BlockAction] = Field(description="Zero to two follow-on actions.")


class DataTable(BaseModel):
    """Raw records. Use when the user asks to list, show or filter rows."""

    type: Literal["data_table"]
    title: str
    columns: list[Column]
    rows: list[list[str]] = Field(
        description="Each row has exactly one pre-formatted string per column, in column order."
    )
    actions: list[BlockAction] = Field(description="Zero to two follow-on actions.")


class TextNote(BaseModel):
    """A written answer. Use when no chart fits, or the request is out of scope."""

    type: Literal["text_note"]
    title: str
    body: str = Field(description="Two or three sentences at most.")
    actions: list[BlockAction] = Field(description="Zero to two follow-on actions.")


Block = StatCard | LineChart | BarChart | DonutChart | DataTable | TextNote

BLOCK_TYPES = ("stat_card", "line_chart", "bar_chart", "donut_chart", "data_table", "text_note")


class AgentTurn(BaseModel):
    """What the model returns for one user turn: a short rationale and a layout.

    Unlike the single-component version this replaced, a turn can compose
    several blocks -- a stat row above a chart above a table -- which is what
    makes "give me a Q3 review" answerable.
    """

    explanation: str = Field(
        description="One short sentence for the chat log explaining what you rendered and why."
    )
    blocks: list[Block] = Field(
        description=(
            "One to four blocks, in the order they should appear top to bottom. "
            "Use several only when the question genuinely needs them."
        )
    )
    follow_ups: list[str] = Field(
        description=(
            "Exactly three short follow-up requests the user could send next, each a "
            "natural continuation of what you just rendered and answerable from this "
            "dataset. Phrase them as the user would type them."
        )
    )


class Turn(BaseModel):
    """One exchange, replayed to the model so follow-ups can say 'that'."""

    role: Literal["user", "assistant"]
    content: str


# A stable code per failure mode, never an exception message. The browser gets
# this plus generic prose; anything more specific would leak internals.
ErrorCode = Literal[
    "missing_api_key",
    "schema_validation_failed",
    "unusable_blocks",
    "upstream_error",
]


class GenerateRequest(BaseModel):
    # Reject unknown keys outright rather than ignoring them, so a client
    # sending the wrong shape finds out immediately.
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(min_length=1, max_length=128)


class ActionRequest(BaseModel):
    """An A2UI action message relayed by the client.

    The renderer posts the action it received from the user; the agent treats
    the carried prompt as the next user turn. This is the client-to-server half
    of the A2UI loop.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=64)
    surface_id: str = Field(default="", max_length=128)
    context: dict[str, str] = Field(default_factory=dict)


# --- Read models for the dashboard endpoint -------------------------------


class HealthResponse(BaseModel):
    status: Literal["ok"]
    model: str
    openai_key_set: bool
    protocol: str
    catalog_id: str


class Period(BaseModel):
    start: str
    end: str


class Kpi(BaseModel):
    label: str
    value: float
    unit: Unit
    delta_pct: float
    delta_direction: Direction
    caption: str


class MonthlyRow(BaseModel):
    month: str
    revenue: float
    expenses: float
    cash_flow: float


class CategoryAmount(BaseModel):
    category: str
    amount: float


class ProductAmount(BaseModel):
    product: str
    amount: float


class RegionAmount(BaseModel):
    region: str
    amount: float


class Transaction(BaseModel):
    date: str
    description: str
    category: str
    amount: float
    status: str


class DashboardResponse(BaseModel):
    """The mock dataset. Typed so OpenAPI documents it and the fixtures are validated."""

    currency: str
    period: Period
    kpis: list[Kpi]
    monthly: list[MonthlyRow]
    expenses_by_category: list[CategoryAmount]
    revenue_by_product: list[ProductAmount]
    revenue_by_region: list[RegionAmount]
    transactions: list[Transaction]
