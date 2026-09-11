from ..xast import detach_node_from_parent

name = "removeXMLProcInst"
description = "removes XML processing instructions"


def fn(root, params, info):
    def enter(node, parent_node):
        if node.name == "xml":
            detach_node_from_parent(node, parent_node)

    return {"instruction": {"enter": enter}}
