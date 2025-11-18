from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Optional


class Command(Protocol):
    def execute(self) -> None:
        ...

    def undo(self) -> None:
        ...


@dataclass
class TextInsertCommand:
    buffer: list[str]
    line: int
    col: int
    text: str
    # snapshot for undo
    _prev_line: Optional[str] = None

    def execute(self) -> None:
        idx = self.line - 1
        pos = self.col - 1
        current = self.buffer[idx]
        self._prev_line = current
        self.buffer[idx] = current[:pos] + self.text + current[pos:]

    def undo(self) -> None:
        if self._prev_line is not None:
            self.buffer[self.line - 1] = self._prev_line


@dataclass
class TextDeleteCommand:
    buffer: list[str]
    line: int
    col: int
    length: int
    _prev_line: Optional[str] = None

    def execute(self) -> None:
        idx = self.line - 1
        pos = self.col - 1
        current = self.buffer[idx]
        self._prev_line = current
        self.buffer[idx] = current[:pos] + current[pos + self.length :]

    def undo(self) -> None:
        if self._prev_line is not None:
            self.buffer[self.line - 1] = self._prev_line


@dataclass
class TextReplaceCommand:
    buffer: list[str]
    line: int
    col: int
    length: int
    text: str
    _prev_line: Optional[str] = None

    def execute(self) -> None:
        idx = self.line - 1
        pos = self.col - 1
        current = self.buffer[idx]
        self._prev_line = current
        self.buffer[idx] = current[:pos] + self.text + current[pos + self.length :]

    def undo(self) -> None:
        if self._prev_line is not None:
            self.buffer[self.line - 1] = self._prev_line
