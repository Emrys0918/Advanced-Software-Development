from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .commands import TextInsertCommand, TextDeleteCommand, TextReplaceCommand, Command
from .editor import Editor


class TextEditorError(Exception):
    pass


@dataclass
class TextEditor(Editor):
    lines: List[str] = field(default_factory=list)
    _undo_stack: List[Command] = field(default_factory=list)
    _redo_stack: List[Command] = field(default_factory=list)

    def __init__(self, path: Path, lines: List[str], modified: bool = False, logging_enabled: bool = False):
        super().__init__(path, modified, logging_enabled)
        self.lines = lines
        self._undo_stack = []
        self._redo_stack = []

    @staticmethod
    def _parse_log_config(line: str) -> tuple[bool, List[str]]:
        parts = line.strip().split()
        if not parts or parts[0] != "#" or len(parts) < 2 or parts[1] != "log":
            return False, []
        
        enabled = True
        excluded = []
        i = 2
        while i < len(parts):
            if parts[i] == "-e" and i + 1 < len(parts):
                excluded.append(parts[i+1])
                i += 2
            else:
                i += 1
        return enabled, excluded

    @staticmethod
    def from_file(path: Path) -> "TextEditor":
        if path.exists():
            content = path.read_text(encoding="utf-8")
            # 保持行结构，末尾换行不强制
            lines = content.split("\n")
        else:
            lines = []
        editor = TextEditor(path=path, lines=lines, modified=not path.exists())
        # 自动日志开关：首行 # log
        if lines:
            enabled, excluded = TextEditor._parse_log_config(lines[0])
            if enabled:
                editor.logging_enabled = True
                editor.excluded_log_commands = excluded
        return editor

    @staticmethod
    def init_new(path: Path, with_log: bool = False) -> "TextEditor":
        lines: List[str] = ["# log"] if with_log else []
        editor = TextEditor(path=path, lines=lines, modified=True)
        if with_log:
            editor.logging_enabled = True
        return editor

    def _ensure_position(self, line: int, col: int) -> None:
        if line < 1 or (len(self.lines) == 0 and (line != 1 or col != 1)):
            raise TextEditorError("空文件只能在1:1位置插入")
        if line > len(self.lines):
            raise TextEditorError("行号或列号越界")
        if col < 1:
            raise TextEditorError("行号或列号越界")
        curr_len = len(self.lines[line - 1]) if self.lines else 0
        if col - 1 > curr_len:
            raise TextEditorError("行号或列号越界")

    def _push_command(self, cmd: Command) -> None:
        cmd.execute()
        self._undo_stack.append(cmd)
        self._redo_stack.clear()
        self.modified = True

    def append(self, text: str) -> None:
        # 追加一行
        self.lines.append(text)
        self.modified = True
        self._redo_stack.clear()
        # 作为不可撤销的简单操作不进入undo栈（更简单也可进入，但这里保持一致性：将其作为单行插入到末行）
        # 将append转化为对末行的插入以支持undo/redo
        if len(self.lines) >= 1:
            # 模拟成对新行的插入：构造插入命令在新的末行基础上
            # 先撤回上面的append直接修改，将真正的插入交给命令，以便undo
            new_line_index = len(self.lines)
            self.lines.pop()  # 回退
            if new_line_index == 1:
                # 空 -> 第一行
                self.lines.append("")
            else:
                self.lines.append("")
            self.insert((new_line_index, 1), text)

    def insert(self, pos: tuple[int, int], text: str) -> None:
        line, col = pos
        # 支持多行插入（拆分为多步）
        parts = text.split("\n")
        if not self.lines:
            # 空文件，只允许1:1
            if not (line == 1 and col == 1):
                raise TextEditorError("空文件只能在1:1位置插入")
            self.lines = [""]

        self._ensure_position(line, col)

        if len(parts) == 1:
            cmd = TextInsertCommand(self.lines, line, col, parts[0])
            self._push_command(cmd)
        else:
            # 多行：先在第一行插入第一段，再在同一行col后断开并插入中间行与最后一段
            # 采取简单实现：在当前位置插入整段，然后替换为分行拼接
            # 更直接的实现：手工重构目标行
            idx = line - 1
            pos = col - 1
            before = self.lines[idx][:pos]
            after = self.lines[idx][pos:]
            new_lines = [before + parts[0]] + parts[1:-1] + [parts[-1] + after]
            # 用替换命令序列实现（保存undo为整体替换）
            original = self.lines[idx]
            # 先将目标行变为第一段
            cmd1 = TextReplaceCommand(self.lines, line, col, len(original) - pos, parts[0])
            cmd1.execute()
            # 在下一行插入中间行
            insert_pos = idx + 1
            for mid in parts[1:-1]:
                self.lines.insert(insert_pos, mid)
                insert_pos += 1
            # 最后一行将剩余拼接
            if parts[-1] or after:
                self.lines.insert(insert_pos, parts[-1] + after)
            self._undo_stack.append(
                _CompositeLineChange(self.lines, line_index=idx, prev_line=original, prev_after_lines_count=len(parts) - 1)
            )
            self._redo_stack.clear()
            self.modified = True

    def delete(self, pos: tuple[int, int], length: int) -> None:
        line, col = pos
        if not self.lines:
            raise TextEditorError("行号或列号越界")
        self._ensure_position(line, col)
        idx = line - 1
        pos0 = col - 1
        leftover = len(self.lines[idx]) - pos0
        if length > leftover:
            raise TextEditorError("删除长度超出行尾")
        cmd = TextDeleteCommand(self.lines, line, col, length)
        self._push_command(cmd)

    def replace(self, pos: tuple[int, int], length: int, text: str) -> None:
        line, col = pos
        if not self.lines:
            raise TextEditorError("行号或列号越界")
        self._ensure_position(line, col)
        idx = line - 1
        pos0 = col - 1
        leftover = len(self.lines[idx]) - pos0
        if length > leftover:
            raise TextEditorError("删除长度超出行尾")
        # 支持多行替换：将等效为删除+插入（可能引入新行）
        if "\n" in text:
            # 先删除该范围，再在删除起点插入多行
            prev_line = self.lines[idx]
            del_cmd = TextDeleteCommand(self.lines, line, col, length)
            del_cmd.execute()
            # 插入多行，采用insert的多行逻辑
            # 但需要一个复合undo
            after_delete_state = list(self.lines)
            self.insert((line, col), text)
            self._undo_stack.append(
                _CompositeReplaceChange(self.lines, line_index=idx, prev_line=prev_line, after_delete_snapshot=after_delete_state)
            )
        else:
            cmd = TextReplaceCommand(self.lines, line, col, length, text)
            self._push_command(cmd)

    def show(self, start: Optional[int] = None, end: Optional[int] = None) -> List[str]:
        if not self.lines:
            return []
        s = 1 if start is None else max(1, start)
        e = len(self.lines) if end is None else min(len(self.lines), end)
        if s > e:
            return []
        return [f"{i}: {self.lines[i-1]}" for i in range(s, e + 1)]

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        cmd = self._undo_stack.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        self.modified = True
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        cmd = self._redo_stack.pop()
        cmd.execute()
        self._undo_stack.append(cmd)
        self.modified = True
        return True

    def save(self) -> None:
        # 将行用\n连接
        content = "\n".join(self.lines)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(content, encoding="utf-8")
        self.modified = False


class _CompositeLineChange:
    # 用于多行插入的复合变更撤销
    def __init__(self, buffer: List[str], line_index: int, prev_line: str, prev_after_lines_count: int) -> None:
        self.buffer = buffer
        self.line_index = line_index
        self.prev_line = prev_line
        self.prev_after_lines_count = prev_after_lines_count

    def execute(self) -> None:
        # 复合变更在insert阶段已执行，这里不做
        pass

    def undo(self) -> None:
        # 将插入的若干后续行删除，并恢复原始目标行
        for _ in range(self.prev_after_lines_count):
            if self.line_index + 1 < len(self.buffer):
                self.buffer.pop(self.line_index + 1)
        self.buffer[self.line_index] = self.prev_line


class _CompositeReplaceChange:
    # 用于多行替换的复合变更撤销
    def __init__(self, buffer: List[str], line_index: int, prev_line: str, after_delete_snapshot: List[str]) -> None:
        self.buffer = buffer
        self.line_index = line_index
        self.prev_line = prev_line
        self.after_delete_snapshot = after_delete_snapshot

    def execute(self) -> None:
        pass

    def undo(self) -> None:
        # 先回到删除后的状态，再恢复目标行
        self.buffer.clear()
        self.buffer.extend(self.after_delete_snapshot)
        if self.line_index < len(self.buffer):
            self.buffer[self.line_index] = self.prev_line
