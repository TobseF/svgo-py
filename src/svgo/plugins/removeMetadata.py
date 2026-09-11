from ..xast import detach_node_from_parent

name = "removeMetadata"
description = "removes <metadata>"


def fn(root, params, info):
    def enter(node, parent_node):
        if node.name == "metadata":
            detach_node_from_parent(node, parent_node)

    return {"element": {"enter": enter}}
