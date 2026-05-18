from __future__ import annotations

from pydantic import BaseModel, Field


class SlideText(BaseModel):
    index: int
    text: str


class Issue(BaseModel):
    slide: int
    fragment: str
    issue_type: str = Field(..., examples=["typo", "spelling", "agreement", "grammar"])
    message: str
    suggestion: str | None = None
    source: str = Field(..., examples=["symspell", "pymorphy3", "language-tool", "rules"])
    start: int | None = None
    end: int | None = None


class CheckResponse(BaseModel):
    filename: str
    slides_count: int
    slides: list[SlideText]
    issues: list[Issue]
