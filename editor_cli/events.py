from dataclasses import dataclass
from typing import Callable, Dict, List, Any


class EventBus:
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {}

    def subscribe(self, event: str, handler: Callable[[Any], None]) -> None:
        self._subscribers.setdefault(event, []).append(handler)

    def unsubscribe(self, event: str, handler: Callable[[Any], None]) -> None:
        if event in self._subscribers:
            self._subscribers[event] = [h for h in self._subscribers[event] if h != handler]

    def emit(self, event: str, payload: Any) -> None:
        for handler in self._subscribers.get(event, []):
            try:
                handler(payload)
            except Exception:
                # 日志监听失败不影响主流程
                pass


@dataclass
class CommandEvent:
    file: str | None
    command: str
    args: str
