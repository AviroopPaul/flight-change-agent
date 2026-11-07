from typing import Any

from pydantic import BaseModel


class FieldBody(BaseModel):
    field: str
    value: Any = None


class FieldOnly(BaseModel):
    field: str


class ResolveBody(BaseModel):
    choice: str


class CategoryBody(BaseModel):
    category: str


class CallBody(BaseModel):
    active: bool
    seconds: int = 0


class CallToken(BaseModel):
    token: str
    url: str
    room: str
