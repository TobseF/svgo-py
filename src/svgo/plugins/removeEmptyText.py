from ..xast import detach_node_from_parent

name = "removeEmptyText"
description = "removes empty <text> elements"


def fn(root, params, info):
    text = params.get("text", True)
    tspan = params.get("tspan", True)
    tref = params.get("tref", True)

    def enter(node, parent_node):
        if text and node.name == "text" and len(node.children) == 0:
            detach_node_from_parent(node, parent_node)
        if tspan and node.name == "tspan" and len(node.children) == 0:
            detach_node_from_parent(node, parent_node)
        if tref and node.name == "tref" and node.attributes.get("xlink:href") is None:
            detach_node_from_parent(node, parent_node)

    return {"element": {"enter": enter}}
