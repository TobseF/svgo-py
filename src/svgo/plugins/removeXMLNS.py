name = "removeXMLNS"
description = "removes xmlns attribute (for inline svg)"


def fn(root, params, info):
    def enter(node):
        if node.name == "svg":
            node.attributes.pop("xmlns", None)

    return {"element": {"enter": lambda node, parent_node: enter(node)}}
