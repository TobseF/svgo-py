"""XAST (XML Abstract Syntax Tree) node model.

Mirrors the plain-object node model used by SVGO's JavaScript implementation
(``lib/types.ts``). Nodes are mutable and allow arbitrary extra attributes to
be attached at runtime (plugins stash computed data such as ``parentNode`` or
style information directly on nodes), so plain classes with ``__dict__`` are
used rather than frozen dataclasses.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Union


class Node:
    """Base class for all XAST nodes."""

    type: str = "node"


class Root(Node):
    type = "root"

    def __init__(self, children: Optional[List["XastChild"]] = None):
        self.children: List["XastChild"] = children if children is not None else []


class Element(Node):
    type = "element"

    def __init__(
        self,
        name: str,
        attributes: Optional[Dict[str, str]] = None,
        children: Optional[List["XastChild"]] = None,
    ):
        self.name = name
        # Attribute insertion order is preserved (dict is ordered in py3.7+),
        # matching JS object property ordering that SVGO relies on.
        self.attributes: Dict[str, str] = attributes if attributes is not None else {}
        self.children: List["XastChild"] = children if children is not None else []


class Text(Node):
    type = "text"

    def __init__(self, value: str):
        self.value = value


class Comment(Node):
    type = "comment"

    def __init__(self, value: str):
        self.value = value


class Cdata(Node):
    type = "cdata"

    def __init__(self, value: str):
        self.value = value


class Instruction(Node):
    type = "instruction"

    def __init__(self, name: str, value: str):
        self.name = name
        self.value = value


class Doctype(Node):
    type = "doctype"

    def __init__(self, name: str, data: Dict[str, str]):
        self.name = name
        self.data = data


XastParent = Union[Root, Element]
XastChild = Union[Element, Text, Comment, Cdata, Instruction, Doctype]
XastNode = Union[Root, Element, Text, Comment, Cdata, Instruction, Doctype]


def detach_node_from_parent(node: XastChild, parent_node: XastParent) -> None:
    """Remove ``node`` from ``parent_node.children`` without breaking loops."""
    parent_node.children = [child for child in parent_node.children if child is not node]
