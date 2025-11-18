from __future__ import annotations

import shlex
from pathlib import Path
from typing import Optional

from .workspace import Workspace


def parse_line_col(token: str) -> tuple[int, int]:
    if ":" not in token:
        raise ValueError
    a, b = token.split(":", 1)
    return int(a), int(b)


def run_repl(root: Path) -> None:
    ws = Workspace.create(root)
    print("简易文本编辑器（Lab1）。输入命令，输入 'exit' 退出。")
    try:
        while True:
            try:
                line = input("> ").strip()
            except EOFError:
                line = "exit"
            if not line:
                continue
            try:
                tokens = shlex.split(line)
            except ValueError as e:
                print(f"参数解析错误: {e}")
                continue
            cmd = tokens[0]
            args = tokens[1:]

            out: Optional[str] = None
            out_lines: Optional[list[str]] = None

            try:
                if cmd == "load" and len(args) == 1:
                    out = ws.load(args[0])
                elif cmd == "save":
                    if not args:
                        out = ws.save()
                    elif len(args) == 1:
                        out = ws.save(args[0])
                    else:
                        out = "用法: save [file|all]"
                elif cmd == "init":
                    if len(args) >= 1:
                        with_log = len(args) >= 2 and args[1] == "with-log"
                        out = ws.init(args[0], with_log=with_log)
                    else:
                        out = "用法: init <file> [with-log]"
                elif cmd == "close":
                    if len(args) == 0:
                        out = ws.close()
                    elif len(args) == 1:
                        out = ws.close(args[0])
                    else:
                        out = "用法: close [file]"
                elif cmd == "edit" and len(args) == 1:
                    out = ws.edit_active(args[0])
                elif cmd == "editor-list":
                    out_lines = ws.editor_list()
                elif cmd == "dir-tree":
                    if len(args) == 0:
                        out_lines = ws.dir_tree()
                    elif len(args) == 1:
                        out_lines = ws.dir_tree(args[0])
                    else:
                        out = "用法: dir-tree [path]"
                elif cmd == "append" and len(args) == 1:
                    out = ws.append(args[0])
                elif cmd == "insert":
                    if len(args) == 2:
                        line_col = parse_line_col(args[0])
                        out = ws.insert(line_col, args[1])
                    else:
                        out = "用法: insert <line:col> \"text\""
                elif cmd == "delete":
                    if len(args) == 2:
                        line_col = parse_line_col(args[0])
                        length = int(args[1])
                        out = ws.delete(line_col, length)
                    else:
                        out = "用法: delete <line:col> <len>"
                elif cmd == "replace":
                    if len(args) == 3:
                        line_col = parse_line_col(args[0])
                        length = int(args[1])
                        out = ws.replace(line_col, length, args[2])
                    else:
                        out = "用法: replace <line:col> <len> \"text\""
                elif cmd == "show":
                    if len(args) == 0:
                        out_lines = ws.show()
                    elif len(args) == 1 and ":" in args[0]:
                        a, b = args[0].split(":", 1)
                        out_lines = ws.show(int(a), int(b))
                    else:
                        out = "用法: show [startLine:endLine]"
                elif cmd == "undo":
                    out = ws.undo()
                elif cmd == "redo":
                    out = ws.redo()
                elif cmd == "log-on":
                    if len(args) == 0:
                        out = ws.log_on()
                    elif len(args) == 1:
                        out = ws.log_on(args[0])
                    else:
                        out = "用法: log-on [file]"
                elif cmd == "log-off":
                    if len(args) == 0:
                        out = ws.log_off()
                    elif len(args) == 1:
                        out = ws.log_off(args[0])
                    else:
                        out = "用法: log-off [file]"
                elif cmd == "log-show":
                    if len(args) == 0:
                        out_lines = ws.log_show()
                    elif len(args) == 1:
                        out_lines = ws.log_show(args[0])
                    else:
                        out = "用法: log-show [file]"
                elif cmd == "exit":
                    # 退出前提示所有未保存文件
                    for p, ed in list(ws.editors.items()):
                        if ed.modified:
                            ans = input(f"{p.name} 已修改，是否保存? (y/n) ").strip().lower()
                            if ans == "y":
                                ed.save()
                                ws._emit("save", file=p)
                    ws.persist()
                    print("已退出。")
                    break
                else:
                    out = f"未知命令: {cmd}"
            except Exception as e:
                out = f"错误: {e}"

            if out_lines is not None:
                for l in out_lines:
                    print(l)
            elif out is not None:
                print(out)
    finally:
        # 兜底持久化
        try:
            ws.persist()
        except Exception:
            pass


def main() -> None:
    root = Path.cwd()
    run_repl(root)


if __name__ == "__main__":
    main()
