"""AST visitor engine. Port of ``lib/util/visit.js``.

A visitor is a mapping of node ``type`` -> callbacks dict with optional
``enter`` and ``exit`` callables, each ``fn(node, parentNode)``. Returning
``VISIT_SKIP`` from an ``enter`` callback skips descending into that node.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

# Sentinel returned by an enter callback to skip visiting a node's children.
VISIT_SKIP = object()

# A Visitor maps node type -> {"enter": fn, "exit": fn}
Visitor = Dict[str, Dict[str, Callable[..., Any]]]


def visit(node: Any, visitor: Visitor, parent_node: Optional[Any] = None) -> None:
    callbacks = visitor.get(node.type)
    if callbacks and callbacks.get("enter"):
        symbol = callbacks["enter"](node, parent_node)
        if symbol is VISIT_SKIP:
            return

    # NOTE: iterate the live children reference (not a copy). SVGO's
    # detach_node_from_parent reassigns ``.children`` to a *new* filtered list
    # rather than mutating in place, so an in-progress iterator over the old
    # list is unaffected -- matching JS ``for...of`` semantics exactly.
    if node.type == "root":
        for child in node.children:
            visit(child, visitor, node)

    if node.type == "element":
        # visit element children only if still attached to parent
        if any(child is node for child in parent_node.children):
            for child in node.children:
                visit(child, visitor, node)

    if callbacks and callbacks.get("exit"):
        callbacks["exit"](node, parent_node)
