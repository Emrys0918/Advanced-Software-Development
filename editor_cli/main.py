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
    print("Emrys的文本编辑器——输入命令或输入 'exit' 退出。")
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
                if cmd == "load":
                    if len(args) == 1:
                        out = ws.load(args[0])
                    else:
                        out = "用法: load <file>"
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
                        out = "用法: init <text|xml|file> [with-log]"
                elif cmd == "close":
                    if len(args) == 0:
                        out = ws.close()
                    elif len(args) == 1:
                        out = ws.close(args[0])
                    else:
                        out = "用法: close [file]"
                elif cmd == "edit":
                    if len(args) == 1:
                        out = ws.edit_active(args[0])
                    else:
                        out = "用法: edit <file>"
                elif cmd == "editor-list":
                    out_lines = ws.editor_list()
                elif cmd == "dir-tree":
                    if len(args) == 0:
                        out_lines = ws.dir_tree()
                    elif len(args) == 1:
                        out_lines = ws.dir_tree(args[0])
                    else:
                        out = "用法: dir-tree [path]"
                elif cmd == "append":
                    if len(args) == 1:
                        out = ws.append(args[0])
                    else:
                        out = "用法: append \"text\""
                elif cmd == "insert":
                    if len(args) == 2:
                        line_col = parse_line_col(args[0])
                        out = ws.insert(line_col, args[1])
                    else:
                        out = "用法: insert <line:col> \"text\""
                elif cmd == "delete":
                    if len(args) == 2:
                        # Text delete: delete <line:col> <len>
                        line_col = parse_line_col(args[0])
                        length = int(args[1])
                        out = ws.delete(line_col, length)
                    elif len(args) == 1:
                        # XML delete: delete <elementId>
                        out = ws.delete_element(args[0])
                    else:
                        out = "用法: delete <line:col> <len> 或 delete <elementId>"
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
                elif cmd == "insert-before":
                    if len(args) >= 3:
                        tag = args[0]
                        new_id = args[1]
                        target_id = args[2]
                        text = args[3] if len(args) > 3 else ""
                        out = ws.insert_before(tag, new_id, target_id, text)
                    else:
                        out = "用法: insert-before <tag> <newId> <targetId> [\"text\"]"
                elif cmd == "append-child":
                    if len(args) >= 3:
                        tag = args[0]
                        new_id = args[1]
                        parent_id = args[2]
                        text = args[3] if len(args) > 3 else ""
                        out = ws.append_child(tag, new_id, parent_id, text)
                    else:
                        out = "用法: append-child <tag> <newId> <parentId> [\"text\"]"
                elif cmd == "edit-id":
                    if len(args) == 2:
                        out = ws.edit_id(args[0], args[1])
                    else:
                        out = "用法: edit-id <oldId> <newId>"
                elif cmd == "edit-text":
                    if len(args) >= 1:
                        element_id = args[0]
                        text = args[1] if len(args) > 1 else ""
                        out = ws.edit_text(element_id, text)
                    else:
                        out = "用法: edit-text <elementId> [\"text\"]"
                elif cmd == "xml-tree":
                    if len(args) == 0:
                        out_lines = ws.xml_tree()
                    elif len(args) == 1:
                        out_lines = ws.xml_tree(args[0])
                    else:
                        out = "用法: xml-tree [file]"
                elif cmd == "spell-check":
                    if len(args) == 0:
                        out_lines = ws.spell_check()
                    elif len(args) == 1:
                        out_lines = ws.spell_check(args[0])
                    else:
                        out = "用法: spell-check [file]"
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
                elif cmd == "stats":
                    if len(args) == 0:
                        out = ws.stats()
                    elif len(args) == 1:
                        out = ws.stats(args[0])
                    else:
                        out = "用法: stats [file]"
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
