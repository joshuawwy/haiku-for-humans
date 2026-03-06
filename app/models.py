from pydantic import BaseModel
from datetime import datetime


class Haiku(BaseModel):
    id: int
    text: str
    author: str
    created_at: datetime
    votes: int = 0


class HaikuPage(BaseModel):
    haikus: list[Haiku]
    has_more: bool


class ValidationResult(BaseModel):
    valid: bool
    message: str
    line_syllables: list[int] | None = None
