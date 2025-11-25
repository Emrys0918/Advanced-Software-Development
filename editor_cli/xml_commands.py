from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict
import xml.etree.ElementTree as ET


@dataclass
class XmlInsertBeforeCommand:
    id_map: Dict[str, ET.Element]
    parent_map: Dict[ET.Element, ET.Element]
    tag: str
    new_id: str
    target_id: str
    text: str
    _created_element: Optional[ET.Element] = None

    def execute(self) -> None:
        target_element = self.id_map[self.target_id]
        parent = self.parent_map[target_element]
        
        # Create new element
        new_element = ET.Element(self.tag)
        new_element.set("id", self.new_id)
        if self.text:
            new_element.text = self.text
            
        # Insert before target
        # ElementTree doesn't have insert_before, so we find index
        index = list(parent).index(target_element)
        parent.insert(index, new_element)
        
        # Update maps
        self.id_map[self.new_id] = new_element
        self.parent_map[new_element] = parent
        self._created_element = new_element

    def undo(self) -> None:
        if self._created_element is not None:
            parent = self.parent_map[self._created_element]
            try:
                parent.remove(self._created_element)
            except ValueError:
                pass
            del self.id_map[self.new_id]
            del self.parent_map[self._created_element]


@dataclass
class XmlAppendChildCommand:
    id_map: Dict[str, ET.Element]
    parent_map: Dict[ET.Element, ET.Element]
    tag: str
    new_id: str
    parent_id: str
    text: str
    _created_element: Optional[ET.Element] = None

    def execute(self) -> None:
        parent = self.id_map[self.parent_id]
        
        new_element = ET.Element(self.tag)
        new_element.set("id", self.new_id)
        if self.text:
            new_element.text = self.text
            
        parent.append(new_element)
        
        self.id_map[self.new_id] = new_element
        self.parent_map[new_element] = parent
        self._created_element = new_element

    def undo(self) -> None:
        if self._created_element is not None:
            parent = self.parent_map[self._created_element]
            parent.remove(self._created_element)
            del self.id_map[self.new_id]
            del self.parent_map[self._created_element]


@dataclass
class XmlEditIdCommand:
    id_map: Dict[str, ET.Element]
    old_id: str
    new_id: str
    _element: Optional[ET.Element] = None

    def execute(self) -> None:
        element = self.id_map[self.old_id]
        self._element = element
        element.set("id", self.new_id)
        del self.id_map[self.old_id]
        self.id_map[self.new_id] = element

    def undo(self) -> None:
        if self._element is not None:
            self._element.set("id", self.old_id)
            del self.id_map[self.new_id]
            self.id_map[self.old_id] = self._element


@dataclass
class XmlEditTextCommand:
    id_map: Dict[str, ET.Element]
    element_id: str
    new_text: str
    _old_text: Optional[str] = None

    def execute(self) -> None:
        element = self.id_map[self.element_id]
        self._old_text = element.text
        element.text = self.new_text if self.new_text else None

    def undo(self) -> None:
        element = self.id_map[self.element_id]
        element.text = self._old_text


@dataclass
class XmlDeleteCommand:
    id_map: Dict[str, ET.Element]
    parent_map: Dict[ET.Element, ET.Element]
    element_id: str
    _deleted_element: Optional[ET.Element] = None
    _parent: Optional[ET.Element] = None
    _index: int = -1
    _deleted_subtree_ids: Optional[Dict[str, ET.Element]] = None

    def execute(self) -> None:
        element = self.id_map[self.element_id]
        parent = self.parent_map[element]
        
        self._deleted_element = element
        self._parent = parent
        self._index = list(parent).index(element)
        
        # Need to track all IDs in the subtree to remove them from id_map
        self._deleted_subtree_ids = {}
        self._collect_ids(element)
        
        parent.remove(element)
        
        # Remove from maps
        for eid in self._deleted_subtree_ids:
            del self.id_map[eid]
            # parent_map cleanup is implicit for children, but we should probably track it if we want to be strict
            # For simplicity, we just rebuild parent_map or rely on the fact that we only need parent_map for the deleted element's parent
            # Actually, we need to remove them from parent_map too to avoid leaks, but for this lab it might be fine.
            # Let's just remove the top element from parent_map
            
        del self.parent_map[element]
        # We should also remove children from parent_map
        self._remove_from_parent_map(element)

    def _collect_ids(self, element: ET.Element) -> None:
        eid = element.get("id")
        if eid:
            self._deleted_subtree_ids[eid] = element
        for child in element:
            self._collect_ids(child)

    def _remove_from_parent_map(self, element: ET.Element) -> None:
        if element in self.parent_map:
            del self.parent_map[element]
        for child in element:
            self._remove_from_parent_map(child)

    def _restore_parent_map(self, element: ET.Element, parent: ET.Element) -> None:
        self.parent_map[element] = parent
        for child in element:
            self._restore_parent_map(child, element)

    def undo(self) -> None:
        if self._deleted_element is not None and self._parent is not None:
            self._parent.insert(self._index, self._deleted_element)
            
            # Restore maps
            if self._deleted_subtree_ids:
                self.id_map.update(self._deleted_subtree_ids)
            
            self._restore_parent_map(self._deleted_element, self._parent)
