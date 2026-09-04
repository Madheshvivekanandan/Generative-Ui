from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.block import Block


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
