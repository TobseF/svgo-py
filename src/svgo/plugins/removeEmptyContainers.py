from ..collections import elemsGroups
from ..style import collect_stylesheet, compute_style
from ..tools import find_references
from ..xast import detach_node_from_parent

name = "removeEmptyContainers"
description = "removes empty container elements"

_container = elemsGroups["container"]


def fn(root, params, info):
    stylesheet = collect_stylesheet(root)
    removed_ids = set()
    uses_by_id = {}

    def enter(node, parent_node):
        if node.name == "use":
            for attr_name, value in node.attributes.items():
                ids = find_references(attr_name, value)
                for id_ in ids:
                    uses_by_id.setdefault(id_, []).append((node, parent_node))

    def exit(node, parent_node):
        if node.name == "svg" or node.name not in _container or len(node.children) != 0:
            return
        if node.name == "pattern" and len(node.attributes) != 0:
            return
        if node.name == "mask" and node.attributes.get("id") is not None:
            return
        if parent_node.type == "element" and parent_node.name == "switch":
            return
        if node.name == "g" and (
            node.attributes.get("filter") is not None
            or compute_style(stylesheet, node).get("filter")
        ):
            return
        detach_node_from_parent(node, parent_node)
        if node.attributes.get("id"):
            removed_ids.add(node.attributes["id"])

    def root_exit(node, parent_node):
        for id_ in removed_ids:
            uses = uses_by_id.get(id_)
            if uses:
                for use_node, use_parent in uses:
                    detach_node_from_parent(use_node, use_parent)

    return {
        "element": {"enter": enter, "exit": exit},
        "root": {"exit": root_exit},
    }
