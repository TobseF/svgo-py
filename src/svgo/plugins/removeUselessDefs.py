from ..collections import elemsGroups
from ..xast import detach_node_from_parent

name = "removeUselessDefs"
description = "removes elements in <defs> without id"

_non_rendering = elemsGroups["nonRendering"]


def _collect_useful_nodes(node, useful_nodes):
    for child in node.children:
        if child.type == "element":
            if child.attributes.get("id") is not None or child.name == "style":
                useful_nodes.append(child)
            else:
                _collect_useful_nodes(child, useful_nodes)


def fn(root, params, info):
    def enter(node, parent_node):
        if node.name == "defs" or (
            node.name in _non_rendering and node.attributes.get("id") is None
        ):
            useful_nodes = []
            _collect_useful_nodes(node, useful_nodes)
            if len(useful_nodes) == 0:
                detach_node_from_parent(node, parent_node)
            node.children = useful_nodes

    return {"element": {"enter": enter}}
