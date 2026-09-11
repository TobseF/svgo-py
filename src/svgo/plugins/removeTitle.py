from ..xast import detach_node_from_parent

name = "removeTitle"
description = "removes <title>"


def fn(root, params, info):
    def enter(node, parent_node):
        if node.name == "title":
            detach_node_from_parent(node, parent_node)

    return {"element": {"enter": enter}}
