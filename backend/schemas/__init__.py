"""The component catalog, as the agent thinks about it — one class per module.

These Pydantic models constrain what the LLM is allowed to emit: they become
the JSON Schema passed to OpenAI as `response_format`, and they validate the
result before anything is compiled to A2UI.

This is deliberately NOT the A2UI wire format. A2UI messages are a flat,
loosely-typed component stream -- excellent for renderers, hostile to
schema-constrained generation. So the agent plans in these typed blocks, and
the `a2ui` package compiles the plan into real A2UI v0.9 messages. The wire and
the client are genuine A2UI; only the agent's internal planning step is typed.

This package re-exports every model, so callers write `from schemas import X`
without caring which file a class lives in.
"""

from schemas.action_request import ActionRequest
from schemas.agent_turn import AgentTurn
from schemas.bar_chart import BarChart
from schemas.block import BLOCK_TYPES, Block
from schemas.block_action import BlockAction
from schemas.category_amount import CategoryAmount
from schemas.column import Column
from schemas.dashboard_response import DashboardResponse
from schemas.data_table import DataTable
from schemas.donut_chart import DonutChart
from schemas.generate_request import GenerateRequest
from schemas.health_response import HealthResponse
from schemas.kpi import Kpi
from schemas.line_chart import LineChart
from schemas.monthly_row import MonthlyRow
from schemas.period import Period
from schemas.point import Point
from schemas.product_amount import ProductAmount
from schemas.region_amount import RegionAmount
from schemas.series import Series
from schemas.slice import Slice
from schemas.stat_card import StatCard
from schemas.text_note import TextNote
from schemas.transaction import Transaction
from schemas.turn import Turn
from schemas.types import Align, Direction, ErrorCode, Unit

__all__ = [
    "ActionRequest",
    "AgentTurn",
    "Align",
    "BarChart",
    "BLOCK_TYPES",
    "Block",
    "BlockAction",
    "CategoryAmount",
    "Column",
    "DashboardResponse",
    "DataTable",
    "Direction",
    "DonutChart",
    "ErrorCode",
    "GenerateRequest",
    "HealthResponse",
    "Kpi",
    "LineChart",
    "MonthlyRow",
    "Period",
    "Point",
    "ProductAmount",
    "RegionAmount",
    "Series",
    "Slice",
    "StatCard",
    "TextNote",
    "Transaction",
    "Turn",
    "Unit",
]
