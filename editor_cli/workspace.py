from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, List, Tuple

from .events import EventBus, CommandEvent
from .state import WorkspaceMemento, EditorState
from .text_editor import TextEditor, TextEditorError
from .logger import FileLogger


@dataclass
class Workspace:
    root: Path
    event_bus: EventBus
    file_logger: FileLogger
    editors: Dict[Path, TextEditor]
    active: Optional[Path]
    state_file: Path

    @staticmethod
    def create(root: Path) -> "Workspace":
        event_bus = EventBus()
        file_logger = FileLogger(event_bus)
        state_file = root / ".workspace_state.json"
        ws = Workspace(root=root, event_bus=event_bus, file_logger=file_logger, editors={}, active=None, state_file=state_file)
        # 尝试恢复
        ws._restore()
        return ws

    def _snapshot(self) -> WorkspaceMemento:
        open_files: List[EditorState] = []
        for p, ed in self.editors.items():
            open_files.append(EditorState(path=str(p), modified=ed.modified, logging_enabled=ed.logging_enabled))
        active_file = str(self.active) if self.active else None
        return WorkspaceMemento(open_files=open_files, active_file=active_file)

    def _restore(self) -> None:
        m = WorkspaceMemento.from_file(self.state_file)
        if not m:
            return
        # 打开文件并恢复轻量状态
        for es in m.open_files:
            p = Path(es.path)
            ed = TextEditor.from_file(p)
            ed.modified = es.modified
            ed.logging_enabled = es.logging_enabled or ed.logging_enabled
            if ed.logging_enabled:
                self.file_logger.set_enabled(ed.path, True)
            self.editors[p] = ed
        if m.active_file:
            ap = Path(m.active_file)
            if ap in self.editors:
                self.active = ap

    def persist(self) -> None:
        m = self._snapshot()
        m.save(self.state_file)

    # 事件辅助
    def _emit(self, command: str, args: str = "", file: Optional[Path] = None) -> None:
        self.event_bus.emit("command", CommandEvent(file=str(file) if file else (str(self.active) if self.active else None), command=command, args=args))

    # 工作区命令
    def load(self, file: str) -> str:
        p = (self.root / file).resolve() if not Path(file).is_absolute() else Path(file)
        ed = TextEditor.from_file(p)
        self.editors[p] = ed
        self.active = p
        if ed.logging_enabled:
            self.file_logger.set_enabled(p, True)
        self._emit("load", p.name, p)
        return f"已加载: {p}"

    def save(self, target: Optional[str] = None) -> str:
        if target is None:
            if not self.active:
                return "无活动文件"
            self.editors[self.active].save()
            self._emit("save", file=self.active)
            return f"已保存: {self.active}"
        if target == "all":
            for p, ed in self.editors.items():
                ed.save()
                self._emit("save", file=p)
            return "已保存所有文件"
        # 可能是具体文件路径
        p = self._resolve_in_workspace(target)
        if p not in self.editors:
            return f"文件未打开: {target}"
        self.editors[p].save()
        self._emit("save", file=p)
        return f"已保存: {p}"

    def init(self, file: str, with_log: bool = False) -> str:
        p = (self.root / file).resolve() if not Path(file).is_absolute() else Path(file)
        ed = TextEditor.init_new(p, with_log=with_log)
        self.editors[p] = ed
        self.active = p
        if ed.logging_enabled:
            self.file_logger.set_enabled(p, True)
        self._emit("init", f"{p.name}{' with-log' if with_log else ''}", p)
        return f"已创建缓冲区: {p}"

    def close(self, target: Optional[str] = None, prompt_fn=input) -> str:
        if target is None:
            if not self.active:
                return "无活动文件"
            p = self.active
        else:
            p = self._resolve_in_workspace(target)
            if p not in self.editors:
                return f"文件未打开: {target}"
        ed = self.editors[p]
        if ed.modified:
            ans = prompt_fn("文件已修改，是否保存? (y/n) ").strip().lower()
            if ans == "y":
                ed.save()
                self._emit("save", file=p)
        del self.editors[p]
        if self.active == p:
            self.active = next(iter(self.editors.keys()), None)
        self._emit("close", file=p)
        return f"已关闭: {p}"

    def edit_active(self, file: str) -> str:
        p = self._resolve_in_workspace(file)
        if p not in self.editors:
            return f"文件未打开: {file}"
        self.active = p
        return f"当前活动文件: {p}"

    def editor_list(self) -> List[str]:
        lines: List[str] = []
        for p, ed in self.editors.items():
            prefix = "* " if self.active == p else "  "
            suf = " [modified]" if ed.modified else ""
            lines.append(f"{prefix}{p.name}{suf}")
        return lines

    def dir_tree(self, path: Optional[str] = None) -> List[str]:
        base = (self.root / path).resolve() if path else self.root
        lines: List[str] = []
        def walk(dir_path: Path, prefix: str = "") -> None:
            items = sorted(dir_path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            for i, item in enumerate(items):
                is_last = i == len(items) - 1
                connector = "└──" if is_last else "├──"
                lines.append(f"{prefix}{connector} {item.name}")
                if item.is_dir():
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    walk(item, new_prefix)
        walk(base)
        return lines

    # 文本编辑命令
    def _current_editor(self) -> Optional[TextEditor]:
        if not self.active:
            return None
        return self.editors.get(self.active)

    def append(self, text: str) -> str:
        ed = self._current_editor()
        if not ed:
            return "无活动文件"
        ed.append(text)
        self._emit("append", f'"{text}"', self.active)
        return "已追加"

    def insert(self, pos: Tuple[int, int], text: str) -> str:
        ed = self._current_editor()
        if not ed:
            return "无活动文件"
        try:
            ed.insert(pos, text)
        except TextEditorError as e:
            return str(e)
        self._emit("insert", f"{pos[0]}:{pos[1]} \"{text}\"", self.active)
        return "已插入"

    def delete(self, pos: Tuple[int, int], length: int) -> str:
        ed = self._current_editor()
        if not ed:
            return "无活动文件"
        try:
            ed.delete(pos, length)
        except TextEditorError as e:
            return str(e)
        self._emit("delete", f"{pos[0]}:{pos[1]} {length}", self.active)
        return "已删除"

    def replace(self, pos: Tuple[int, int], length: int, text: str) -> str:
        ed = self._current_editor()
        if not ed:
            return "无活动文件"
        try:
            ed.replace(pos, length, text)
        except TextEditorError as e:
            return str(e)
        self._emit("replace", f"{pos[0]}:{pos[1]} {length} \"{text}\"", self.active)
        return "已替换"

    def show(self, start: Optional[int] = None, end: Optional[int] = None) -> List[str]:
        ed = self._current_editor()
        if not ed:
            return []
        return ed.show(start, end)

    def undo(self) -> str:
        ed = self._current_editor()
        if not ed:
            return "无活动文件"
        ok = ed.undo()
        if ok:
            self._emit("undo", file=self.active)
            return "已撤销"
        return "无可撤销操作"

    def redo(self) -> str:
        ed = self._current_editor()
        if not ed:
            return "无活动文件"
        ok = ed.redo()
        if ok:
            self._emit("redo", file=self.active)
            return "已重做"
        return "无可重做操作"

    # 日志命令
    def log_on(self, file: Optional[str] = None) -> str:
        p = self._resolve_for_log(file)
        if not p:
            return "无活动文件"
        ed = self.editors[p]
        ed.logging_enabled = True
        self.file_logger.set_enabled(p, True)
        return f"已启用日志: {p.name}"

    def log_off(self, file: Optional[str] = None) -> str:
        p = self._resolve_for_log(file)
        if not p:
            return "无活动文件"
        ed = self.editors[p]
        ed.logging_enabled = False
        self.file_logger.set_enabled(p, False)
        return f"已关闭日志: {p.name}"

    def log_show(self, file: Optional[str] = None) -> List[str]:
        p = self._resolve_for_log(file)
        if not p:
            return []
        content = self.file_logger.show(p)
        return content.splitlines()

    # 帮助方法
    def _resolve_in_workspace(self, file: str) -> Path:
        return (self.root / file).resolve() if not Path(file).is_absolute() else Path(file)

    def _resolve_for_log(self, file: Optional[str]) -> Optional[Path]:
        if file is None:
            return self.active
        p = self._resolve_in_workspace(file)
        return p if p in self.editors else None
