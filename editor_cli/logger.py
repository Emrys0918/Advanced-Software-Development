from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Set

from .events import EventBus, CommandEvent


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d %H:%M:%S")


class FileLogger:
    """按文件记录命令日志。使用观察者监听命令事件。"""

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus
        self.enabled_files: Dict[Path, List[str]] = {}
        self.session_started: Set[Path] = set()
        self.event_bus.subscribe("command", self._on_command)

    def set_enabled(self, file: Path, enabled: bool, excluded_commands: List[str] = []) -> None:
        if enabled:
            self.enabled_files[file] = excluded_commands
        else:
            if file in self.enabled_files:
                del self.enabled_files[file]

    def is_enabled(self, file: Path) -> bool:
        return file in self.enabled_files

    def show(self, file: Path) -> str:
        log_path = file.parent / f".{file.name}.log"
        if not log_path.exists():
            return ""
        return log_path.read_text(encoding="utf-8")

    def _ensure_session(self, file: Path) -> None:
        if file in self.session_started:
            return
        log_path = file.parent / f".{file.name}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"session start at {_ts()}\n")
        self.session_started.add(file)

    def _on_command(self, evt: CommandEvent) -> None:
        if not evt.file:
            return
        file = Path(evt.file)
        if file not in self.enabled_files:
            return
        
        excluded = self.enabled_files[file]
        if evt.command in excluded:
            return

        self._ensure_session(file)
        log_path = file.parent / f".{file.name}.log"
        with log_path.open("a", encoding="utf-8") as f:
            if evt.args:
                f.write(f"{_ts()} {evt.command} {evt.args}\n")
            else:
                f.write(f"{_ts()} {evt.command}\n")
