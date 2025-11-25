from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from .events import EventBus, CommandEvent


class SessionTimer:
    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus
        self.accumulated_time: Dict[str, float] = {}
        self.active_file: Optional[str] = None
        self.last_switch_time: float = 0.0
        
        # Subscribe to events
        # We need to know when active file changes.
        # The workspace emits 'load', 'init', 'edit', 'close'.
        # But these events might be emitted AFTER the action.
        # We need to capture the moment BEFORE the switch to update the old file's time.
        # Or we can just rely on the fact that we get a notification.
        # But the notification payload in Lab 1 was just file path.
        # We might need to hook into Workspace more directly or add a specific 'active_file_changed' event.
        # For now, let's assume we can listen to command events, but they might be too late or ambiguous.
        # Actually, Lab 1 Workspace emits 'load', 'init', 'edit', 'close'.
        # 'edit' <file> -> switches to file.
        # 'close' [file] -> closes file.
        
        # Let's add a specific method to be called by Workspace, or improve EventBus usage.
        # Since I can modify Workspace, I will add explicit calls or a dedicated event.
        # Let's add 'file_switched' event to Workspace.
        
        self.event_bus.subscribe("file_switched", self._on_file_switched)
        self.event_bus.subscribe("file_closed", self._on_file_closed)

    def _update_current(self) -> None:
        if self.active_file:
            now = time.time()
            delta = now - self.last_switch_time
            self.accumulated_time[self.active_file] = self.accumulated_time.get(self.active_file, 0.0) + delta
            self.last_switch_time = now

    def _on_file_switched(self, new_file: str) -> None:
        self._update_current()
        self.active_file = new_file
        self.last_switch_time = time.time()
        # Ensure entry exists
        if new_file and new_file not in self.accumulated_time:
            self.accumulated_time[new_file] = 0.0

    def _on_file_closed(self, file: str) -> None:
        if self.active_file == file:
            self._update_current()
            self.active_file = None
        if file in self.accumulated_time:
            del self.accumulated_time[file]

    def get_formatted_duration(self, file: str) -> str:
        # Calculate current duration including pending time if it's active
        duration = self.accumulated_time.get(file, 0.0)
        if file == self.active_file:
            duration += time.time() - self.last_switch_time
            
        if duration < 60:
            return f"{int(duration)}秒"
        elif duration < 3600:
            return f"{int(duration // 60)}分钟"
        elif duration < 86400:
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            return f"{hours}小时{minutes}分钟"
        else:
            days = int(duration // 86400)
            hours = int((duration % 86400) // 3600)
            return f"{days}天{hours}小时"
