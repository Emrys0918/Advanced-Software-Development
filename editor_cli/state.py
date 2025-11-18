from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
from typing import Dict, List, Optional


@dataclass
class EditorState:
    path: str
    modified: bool
    logging_enabled: bool


@dataclass
class WorkspaceMemento:
    open_files: List[EditorState]
    active_file: Optional[str]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @staticmethod
    def from_file(path: Path) -> Optional[WorkspaceMemento]:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            open_files = [EditorState(**e) for e in data.get("open_files", [])]
            active = data.get("active_file")
            return WorkspaceMemento(open_files=open_files, active_file=active)
        except Exception:
            return None

    def save(self, path: Path) -> None:
        path.write_text(self.to_json(), encoding="utf-8")
