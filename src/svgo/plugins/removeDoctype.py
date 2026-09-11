from ..xast import detach_node_from_parent

name = "removeDoctype"
description = "removes doctype declaration"


def fn(root, params, info):
    def enter(node, parent_node):
        detach_node_from_parent(node, parent_node)

    return {"doctype": {"enter": enter}}
