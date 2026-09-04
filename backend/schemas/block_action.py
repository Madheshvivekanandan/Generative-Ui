from __future__ import annotations

from pydantic import BaseModel, Field


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
