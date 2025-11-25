from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional


class Editor(ABC):
    def __init__(self, path: Path, modified: bool = False, logging_enabled: bool = False):
        self.path = path
        self.modified = modified
        self.logging_enabled = logging_enabled
        self.excluded_log_commands: List[str] = []

    @abstractmethod
    def save(self) -> None:
        pass

    @abstractmethod
    def undo(self) -> bool:
        pass

    @abstractmethod
    def redo(self) -> bool:
        pass
