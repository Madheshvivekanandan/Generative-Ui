"""The component catalog.

These Pydantic models are the contract in both directions: they are converted
to a JSON Schema that constrains what the LLM is allowed to emit, and they are
what the response is validated against before anything reaches the browser.
Adding a component to the dashboard means adding a model here and a renderer
in the frontend -- nothing else.
"""

from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, Field

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


class StatCard(BaseModel):
    """A single headline number. Use when the answer is one figure."""

    type: Literal["stat_card"]
    title: str
    label: str = Field(description="What the number measures, e.g. 'Net Cash Flow'.")
    value: float
    unit: Unit
    delta_pct: float = Field(description="Percent change vs. the comparison period; 0 if unknown.")
    delta_direction: Direction
    caption: str = Field(description="Short context line, e.g. 'vs. prior 12 months'.")


class LineChart(BaseModel):
    """Change over time. Use for anything trending across months."""

    type: Literal["line_chart"]
    title: str
    x_label: str
    y_label: str
    unit: Unit
    series: list[Series] = Field(description="One to four series. More than four is unreadable.")


class BarChart(BaseModel):
    """Comparison across categories, or period-over-period totals."""

    type: Literal["bar_chart"]
    title: str
    x_label: str
    y_label: str
    unit: Unit
    stacked: bool = Field(description="True only when the series sum to a meaningful total.")
    series: list[Series] = Field(description="One to four series sharing the same x values.")


class DonutChart(BaseModel):
    """Composition of a whole. Only when parts genuinely sum to 100%."""

    type: Literal["donut_chart"]
    title: str
    unit: Unit
    slices: list[Slice] = Field(
        description="Two to six slices, largest first. Roll up the tail into 'Other'."
    )


class DataTable(BaseModel):
    """Raw records. Use when the user asks to list, show or filter rows."""

    type: Literal["data_table"]
    title: str
    columns: list[Column]
    rows: list[list[str]] = Field(
        description="Each row has exactly one pre-formatted string per column, in column order."
    )


class TextNote(BaseModel):
    """A written answer. Use when no chart fits, or the request is out of scope."""

    type: Literal["text_note"]
    title: str
    body: str = Field(description="Two or three sentences at most.")


Component = Union[StatCard, LineChart, BarChart, DonutChart, DataTable, TextNote]

COMPONENT_TYPES = ("stat_card", "line_chart", "bar_chart", "donut_chart", "data_table", "text_note")


class UIDecision(BaseModel):
    """What the model returns: a one-line rationale plus the component to render."""

    explanation: str = Field(
        description="One short sentence for the chat log explaining what you rendered and why."
    )
    component: Component = Field(description="The component to add to the dashboard.")
    follow_ups: list[str] = Field(
        description=(
            "Exactly three short follow-up requests the user could send next, each a "
            "natural continuation of what you just rendered and answerable from this "
            "dataset. Phrase them as the user would type them."
        )
    )


class GenerateRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class GenerateResponse(BaseModel):
    """Always returned with HTTP 200 so the frontend has a single happy path."""

    ok: bool
    explanation: str
    component: Component
    follow_ups: list[str] = Field(
        default_factory=list, description="Suggested next requests, shown as chips in the chat."
    )
    fallback: bool = Field(
        default=False, description="True when the component is a server-generated stand-in."
    )
    error: str | None = None
