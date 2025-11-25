from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Union

from .events import EventBus, CommandEvent
from .state import WorkspaceMemento, EditorState
from .editor import Editor
from .text_editor import TextEditor, TextEditorError
from .xml_editor import XmlEditor, XmlEditorError
from .logger import FileLogger
from .statistics import SessionTimer
from .spell_checker import MockSpellChecker, SpellCheckerAdapter, RealSpellChecker


@dataclass
class Workspace:
    root: Path
    event_bus: EventBus
    file_logger: FileLogger
    session_timer: SessionTimer
    spell_checker: SpellCheckerAdapter
    editors: Dict[Path, Editor]
    active: Optional[Path]
    state_file: Path

    @staticmethod
    def create(root: Path) -> "Workspace":
        event_bus = EventBus()
        file_logger = FileLogger(event_bus)
        session_timer = SessionTimer(event_bus)
        
        # Try to use RealSpellChecker, fallback to Mock
        spell_checker = RealSpellChecker()
        if not spell_checker.available:
            spell_checker = MockSpellChecker()
            
        state_file = root / ".workspace_state.json"
        ws = Workspace(
            root=root, 
            event_bus=event_bus, 
            file_logger=file_logger, 
            session_timer=session_timer,
            spell_checker=spell_checker,
            editors={}, 
            active=None, 
            state_file=state_file
        )
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
            # Detect type by extension
            if p.suffix == ".xml":
                ed = XmlEditor.from_file(p)
            else:
                ed = TextEditor.from_file(p)
                
            ed.modified = es.modified
            ed.logging_enabled = es.logging_enabled or ed.logging_enabled
            if ed.logging_enabled:
                self.file_logger.set_enabled(ed.path, True, ed.excluded_log_commands)
            self.editors[p] = ed
        if m.active_file:
            ap = Path(m.active_file)
            if ap in self.editors:
                self.active = ap
                self.event_bus.emit("file_switched", str(ap))

    def persist(self) -> None:
        m = self._snapshot()
        m.save(self.state_file)

    # 事件辅助
    def _emit(self, command: str, args: str = "", file: Optional[Path] = None) -> None:
        self.event_bus.emit("command", CommandEvent(file=str(file) if file else (str(self.active) if self.active else None), command=command, args=args))

    # 工作区命令
    def load(self, file: str) -> str:
        p = (self.root / file).resolve() if not Path(file).is_absolute() else Path(file)
        
        if p.suffix == ".xml":
            ed = XmlEditor.from_file(p)
        else:
            ed = TextEditor.from_file(p)
            
        self.editors[p] = ed
        self.active = p
        if ed.logging_enabled:
            self.file_logger.set_enabled(p, True, ed.excluded_log_commands)
        
        self._emit("load", p.name, p)
        self.event_bus.emit("file_switched", str(p))
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

    def init(self, file_type_or_name: str, with_log: bool = False) -> str:
        # Lab 2: init <text|xml> [with-log]
        # But Lab 1 was init <file> [with-log]
        # We need to support both or check if the first arg is 'text'/'xml' or a filename.
        # Lab 2 spec says: init <text|xml> [with-log]
        # It creates a new buffer. Does it name it?
        # "创建一个未保存的新缓冲文件"
        # Lab 1: init <file>
        # Lab 2 spec implies we might need to generate a name or ask for it?
        # Wait, Lab 2 spec: "init <text|xml> [with-log]"
        # Example: "init text with-log"
        # It doesn't specify filename.
        # Maybe it creates "untitled.txt" or similar?
        # Or maybe I should interpret it as: if arg is 'text' or 'xml', create untitled.
        # But Lab 1 `init test.txt` is still valid?
        # The spec says "In Lab 2, compared to Lab 1 command set... Added and Changed:"
        # "init <text|xml> [with-log]" is listed under Workspace Commands.
        # It seems to replace the old init? Or maybe it's an overload.
        # If I type `init test.txt`, is it text or xml?
        # I'll assume if the arg is 'text' or 'xml', it's the new mode.
        # If it has an extension or doesn't match 'text'/'xml', it's the old mode (Lab 1 compatibility).
        # But wait, if I create a new buffer without a name, how do I save it? `save <file>`?
        # Lab 1 `save` supports `save [file]`.
        # So I can create an untitled file and then save it with a name.
        # I'll generate a unique name like `untitled_1.txt` or `untitled_1.xml`.
        
        if file_type_or_name in ("text", "xml"):
            # New mode
            ext = ".txt" if file_type_or_name == "text" else ".xml"
            # Find a unique name
            i = 1
            while True:
                name = f"untitled_{i}{ext}"
                p = self.root / name
                if not p.exists() and p not in self.editors:
                    break
                i += 1
            
            if file_type_or_name == "xml":
                ed = XmlEditor.init_new(p, with_log=with_log)
            else:
                ed = TextEditor.init_new(p, with_log=with_log)
        else:
            # Old mode (Lab 1)
            file = file_type_or_name
            p = (self.root / file).resolve() if not Path(file).is_absolute() else Path(file)
            if p.suffix == ".xml":
                ed = XmlEditor.init_new(p, with_log=with_log)
            else:
                ed = TextEditor.init_new(p, with_log=with_log)

        self.editors[p] = ed
        self.active = p
        if ed.logging_enabled:
            self.file_logger.set_enabled(p, True, ed.excluded_log_commands)
        
        self._emit("init", f"{file_type_or_name}{' with-log' if with_log else ''}", p)
        self.event_bus.emit("file_switched", str(p))
        return f"已创建缓冲区: {p.name}"

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
            ans = prompt_fn(f"{p.name} 文件已修改，是否保存? (y/n) ").strip().lower()
            if ans == "y":
                ed.save()
                self._emit("save", file=p)
        
        self.event_bus.emit("file_closed", str(p))
        del self.editors[p]
        
        if self.active == p:
            self.active = next(iter(self.editors.keys()), None)
            if self.active:
                self.event_bus.emit("file_switched", str(self.active))
            else:
                # No active file
                pass
                
        self._emit("close", file=p)
        return f"已关闭: {p}"

    def edit_active(self, file: str) -> str:
        p = self._resolve_in_workspace(file)
        if p not in self.editors:
            return f"文件未打开: {file}"
        self.active = p
        self.event_bus.emit("file_switched", str(p))
        return f"当前活动文件: {p}"

    def editor_list(self) -> List[str]:
        lines: List[str] = []
        for p, ed in self.editors.items():
            prefix = "* " if self.active == p else "  "
            suf = " [modified]" if ed.modified else ""
            duration = self.session_timer.get_formatted_duration(str(p))
            lines.append(f"{prefix}{p.name}{suf} ({duration})")
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
    def _current_text_editor(self) -> Optional[TextEditor]:
        if not self.active:
            return None
        ed = self.editors.get(self.active)
        if isinstance(ed, TextEditor):
            return ed
        return None

    def _current_xml_editor(self) -> Optional[XmlEditor]:
        if not self.active:
            return None
        ed = self.editors.get(self.active)
        if isinstance(ed, XmlEditor):
            return ed
        return None

    def append(self, text: str) -> str:
        ed = self._current_text_editor()
        if not ed:
            return "当前不是文本文件"
        ed.append(text)
        self._emit("append", f'"{text}"', self.active)
        return "已追加"

    def insert(self, pos: Tuple[int, int], text: str) -> str:
        ed = self._current_text_editor()
        if not ed:
            return "当前不是文本文件"
        try:
            ed.insert(pos, text)
        except TextEditorError as e:
            return str(e)
        self._emit("insert", f"{pos[0]}:{pos[1]} \"{text}\"", self.active)
        return "已插入"

    def delete(self, pos: Tuple[int, int], length: int) -> str:
        ed = self._current_text_editor()
        if not ed:
            return "当前不是文本文件"
        try:
            ed.delete(pos, length)
        except TextEditorError as e:
            return str(e)
        self._emit("delete", f"{pos[0]}:{pos[1]} {length}", self.active)
        return "已删除"

    def replace(self, pos: Tuple[int, int], length: int, text: str) -> str:
        ed = self._current_text_editor()
        if not ed:
            return "当前不是文本文件"
        try:
            ed.replace(pos, length, text)
        except TextEditorError as e:
            return str(e)
        self._emit("replace", f"{pos[0]}:{pos[1]} {length} \"{text}\"", self.active)
        return "已替换"

    def show(self, start: Optional[int] = None, end: Optional[int] = None) -> List[str]:
        ed = self._current_text_editor()
        if not ed:
            return []
        return ed.show(start, end)

    # XML编辑命令
    def insert_before(self, tag: str, new_id: str, target_id: str, text: str = "") -> str:
        ed = self._current_xml_editor()
        if not ed:
            return "当前不是XML文件"
        try:
            ed.insert_before(tag, new_id, target_id, text)
        except XmlEditorError as e:
            return str(e)
        self._emit("insert-before", f"{tag} {new_id} {target_id} \"{text}\"", self.active)
        return "已插入元素"

    def append_child(self, tag: str, new_id: str, parent_id: str, text: str = "") -> str:
        ed = self._current_xml_editor()
        if not ed:
            return "当前不是XML文件"
        try:
            ed.append_child(tag, new_id, parent_id, text)
        except XmlEditorError as e:
            return str(e)
        self._emit("append-child", f"{tag} {new_id} {parent_id} \"{text}\"", self.active)
        return "已追加子元素"

    def edit_id(self, old_id: str, new_id: str) -> str:
        ed = self._current_xml_editor()
        if not ed:
            return "当前不是XML文件"
        try:
            ed.edit_id(old_id, new_id)
        except XmlEditorError as e:
            return str(e)
        self._emit("edit-id", f"{old_id} {new_id}", self.active)
        return "已修改ID"

    def edit_text(self, element_id: str, text: str = "") -> str:
        ed = self._current_xml_editor()
        if not ed:
            return "当前不是XML文件"
        try:
            ed.edit_text(element_id, text)
        except XmlEditorError as e:
            return str(e)
        self._emit("edit-text", f"{element_id} \"{text}\"", self.active)
        return "已修改文本"

    def delete_element(self, element_id: str) -> str:
        ed = self._current_xml_editor()
        if not ed:
            return "当前不是XML文件"
        try:
            ed.delete(element_id)
        except XmlEditorError as e:
            return str(e)
        self._emit("delete", f"{element_id}", self.active)
        return "已删除元素"

    def xml_tree(self, file: Optional[str] = None) -> List[str]:
        if file:
            p = self._resolve_in_workspace(file)
            if p not in self.editors:
                return []
            ed = self.editors[p]
        else:
            ed = self.editors.get(self.active)
            
        if isinstance(ed, XmlEditor):
            return ed.show_tree()
        return []

    # 拼写检查
    def spell_check(self, file: Optional[str] = None) -> List[str]:
        if file:
            p = self._resolve_in_workspace(file)
            if p not in self.editors:
                return ["文件未打开"]
            ed = self.editors[p]
        else:
            ed = self.editors.get(self.active)
            if not ed:
                return ["无活动文件"]
        
        results = []
        if isinstance(ed, TextEditor):
            for i, line in enumerate(ed.lines):
                errors = self.spell_checker.check(line)
                for wrong, right in errors:
                    # Find column (simple approximation)
                    col = line.find(wrong) + 1
                    results.append(f"第{i+1}行，第{col}列: \"{wrong}\" -> 建议: {right}")
        elif isinstance(ed, XmlEditor):
            # Traverse XML tree and check text
            def traverse(el):
                if el.text:
                    errors = self.spell_checker.check(el.text)
                    for wrong, right in errors:
                        eid = el.get("id", "unknown")
                        results.append(f"元素 {eid}: \"{wrong}\" -> 建议: {right}")
                for child in el:
                    traverse(child)
            if ed.root_element:
                traverse(ed.root_element)
        
        if not results:
            return ["未发现拼写错误"]
        return ["拼写检查结果:"] + results

    def undo(self) -> str:
        ed = self.editors.get(self.active)
        if not ed:
            return "无活动文件"
        ok = ed.undo()
        if ok:
            self._emit("undo", file=self.active)
            return "已撤销"
        return "无可撤销操作"

    def redo(self) -> str:
        ed = self.editors.get(self.active)
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
        self.file_logger.set_enabled(p, True, ed.excluded_log_commands)
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

    def stats(self, file: Optional[str] = None) -> str:
        if file:
            p = self._resolve_in_workspace(file)
            if p not in self.editors:
                return f"文件未打开: {file}"
        else:
            p = self.active
            if not p:
                return "无活动文件"
        
        duration = self.session_timer.get_formatted_duration(str(p))
        return f"{p.name}: {duration}"
