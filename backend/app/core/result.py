from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Ok:
    value: Any = None
    ok: bool = True


@dataclass(frozen=True)
class Err:
    message: str
    ok: bool = False
