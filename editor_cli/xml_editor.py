from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional
import xml.etree.ElementTree as ET

from .editor import Editor
from .commands import Command
from .xml_commands import (
    XmlInsertBeforeCommand,
    XmlAppendChildCommand,
    XmlEditIdCommand,
    XmlEditTextCommand,
    XmlDeleteCommand,
)


class XmlEditorError(Exception):
    pass


@dataclass
class XmlEditor(Editor):
    root_element: Optional[ET.Element] = None
    tree: Optional[ET.ElementTree] = None
    id_map: Dict[str, ET.Element] = field(default_factory=dict)
    parent_map: Dict[ET.Element, ET.Element] = field(default_factory=dict)
    _undo_stack: List[Command] = field(default_factory=list)
    _redo_stack: List[Command] = field(default_factory=list)

    def __init__(self, path: Path, modified: bool = False, logging_enabled: bool = False):
        super().__init__(path, modified, logging_enabled)
        self.id_map = {}
        self.parent_map = {}
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
    def from_file(path: Path) -> "XmlEditor":
        editor = XmlEditor(path, modified=False)
        if path.exists():
            try:
                # Check for # log in first line if it's a text file, but XML parser might fail.
                # Spec says: <?xml ... ?> must be first line UNLESS first line is # log.
                # So we read lines first.
                with open(path, "r", encoding="utf-8") as f:
                    first_line = f.readline().strip()
                
                enabled, excluded = XmlEditor._parse_log_config(first_line)
                
                if enabled:
                    editor.logging_enabled = True
                    editor.excluded_log_commands = excluded
                    # Parse from second line onwards? Or just parse the file and ignore the comment?
                    # Standard XML parsers won't like "# log" at the top.
                    # We might need to read the content, strip the first line if it is # log, then parse.
                    content = path.read_text(encoding="utf-8")
                    lines = content.splitlines()
                    # Re-check first line in content to be sure
                    if lines and XmlEditor._parse_log_config(lines[0])[0]:
                        xml_content = "\n".join(lines[1:])
                    else:
                        xml_content = content
                    
                    if not xml_content.strip():
                         # Empty or just log
                         editor.root_element = None
                    else:
                        editor.root_element = ET.fromstring(xml_content)
                        editor.tree = ET.ElementTree(editor.root_element)
                else:
                    editor.tree = ET.parse(path)
                    editor.root_element = editor.tree.getroot()
                
                if editor.root_element is not None:
                    editor._build_maps()
            except ET.ParseError:
                # Handle empty or invalid XML
                editor.root_element = None
        else:
            editor.modified = True
            # Initialize default root for new files
            editor.root_element = ET.Element("root")
            editor.root_element.set("id", "root")
            editor.tree = ET.ElementTree(editor.root_element)
            editor._build_maps()
        return editor

    @staticmethod
    def init_new(path: Path, with_log: bool = False) -> "XmlEditor":
        editor = XmlEditor(path, modified=True, logging_enabled=with_log)
        # Initialize with default root
        editor.root_element = ET.Element("root")
        editor.root_element.set("id", "root")
        editor.tree = ET.ElementTree(editor.root_element)
        editor._build_maps()
        return editor

    def _build_maps(self) -> None:
        self.id_map = {}
        self.parent_map = {}
        if self.root_element is None:
            return
            
        # Recursive build
        def traverse(el: ET.Element, parent: Optional[ET.Element]):
            eid = el.get("id")
            if eid:
                self.id_map[eid] = el
            if parent is not None:
                self.parent_map[el] = parent
            for child in el:
                traverse(child, el)
        
        traverse(self.root_element, None)

    def _push_command(self, cmd: Command) -> None:
        cmd.execute()
        self._undo_stack.append(cmd)
        self._redo_stack.clear()
        self.modified = True

    def insert_before(self, tag: str, new_id: str, target_id: str, text: str = "") -> None:
        if new_id in self.id_map:
            raise XmlEditorError(f"元素ID已存在: {new_id}")
        if target_id not in self.id_map:
            raise XmlEditorError(f"目标元素不存在: {target_id}")
        
        target_element = self.id_map[target_id]
        if target_element == self.root_element:
            raise XmlEditorError("不能在根元素前插入元素")
            
        cmd = XmlInsertBeforeCommand(self.id_map, self.parent_map, tag, new_id, target_id, text)
        self._push_command(cmd)

    def append_child(self, tag: str, new_id: str, parent_id: str, text: str = "") -> None:
        if new_id in self.id_map:
            raise XmlEditorError(f"元素ID已存在: {new_id}")
        if parent_id not in self.id_map:
            raise XmlEditorError(f"父元素不存在: {parent_id}")
            
        cmd = XmlAppendChildCommand(self.id_map, self.parent_map, tag, new_id, parent_id, text)
        self._push_command(cmd)

    def edit_id(self, old_id: str, new_id: str) -> None:
        if old_id not in self.id_map:
            raise XmlEditorError(f"元素不存在: {old_id}")
        if new_id in self.id_map:
            raise XmlEditorError(f"目标ID已存在: {new_id}")
        if self.id_map[old_id] == self.root_element:
            raise XmlEditorError("不建议修改根元素ID")
            
        cmd = XmlEditIdCommand(self.id_map, old_id, new_id)
        self._push_command(cmd)

    def edit_text(self, element_id: str, text: str = "") -> None:
        if element_id not in self.id_map:
            raise XmlEditorError(f"元素不存在: {element_id}")
            
        cmd = XmlEditTextCommand(self.id_map, element_id, text)
        self._push_command(cmd)

    def delete(self, element_id: str) -> None:
        if element_id not in self.id_map:
            raise XmlEditorError(f"元素不存在: {element_id}")
        if self.id_map[element_id] == self.root_element:
            raise XmlEditorError("不能删除根元素")
            
        cmd = XmlDeleteCommand(self.id_map, self.parent_map, element_id)
        self._push_command(cmd)

    def show_tree(self) -> List[str]:
        if self.root_element is None:
            return []
        
        lines = []
        
        def format_attrs(el: ET.Element) -> str:
            # id first, then others
            attrs = []
            eid = el.get("id")
            if eid:
                attrs.append(f'id="{eid}"')
            for k, v in el.attrib.items():
                if k != "id":
                    attrs.append(f'{k}="{v}"')
            return ", ".join(attrs)

        def traverse(el: ET.Element, prefix: str, is_last: bool, is_root: bool):
            connector = ""
            if not is_root:
                connector = "└── " if is_last else "├── "
            
            attrs_str = format_attrs(el)
            line = f"{prefix}{connector}{el.tag}"
            if attrs_str:
                line += f" [{attrs_str}]"
            lines.append(line)
            
            new_prefix = prefix
            if not is_root:
                new_prefix += "    " if is_last else "│   "
            
            children = list(el)
            has_text = el.text and el.text.strip()
            
            for i, child in enumerate(children):
                is_last_child = (i == len(children) - 1) and not has_text
                traverse(child, new_prefix, is_last_child, False)
                
            if has_text:
                connector = "└── "
                lines.append(f"{new_prefix}{connector}\"{el.text.strip()}\"")

        traverse(self.root_element, "", True, True)
        return lines

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
        if self.root_element is None:
            return
            
        # Indent for pretty printing
        ET.indent(self.tree, space="    ", level=0)
        
        output = ""
        if self.logging_enabled:
            output += "# log\n"
            
        # We need to write to string first to handle the declaration manually if needed, 
        # or just use write with xml_declaration=True
        # But if we have # log, we can't have xml declaration at the very top.
        # Spec says: <?xml ... ?> must be first line UNLESS first line is # log.
        
        # Let's generate XML string
        xml_str = ET.tostring(self.root_element, encoding="unicode", method="xml")
        # Add declaration manually if not present (tostring doesn't add it by default usually unless specified)
        # Actually ET.tostring doesn't support xml_declaration argument in older versions, but 3.8+ does.
        # Let's construct it manually to be safe and consistent.
        
        declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        
        if self.logging_enabled:
            final_content = "# log\n" + declaration + xml_str
        else:
            final_content = declaration + xml_str
            
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(final_content, encoding="utf-8")
        self.modified = False
