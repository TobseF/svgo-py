from ..xast import detach_node_from_parent

name = "removeStyleElement"
description = "removes <style> element"


def fn(root, params, info):
    def enter(node, parent_node):
        if node.name == "style":
            detach_node_from_parent(node, parent_node)

    return {"element": {"enter": enter}}
