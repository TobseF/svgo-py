from ..collections import attrsGroups

name = "removeEmptyAttrs"
description = "removes empty attributes"


def fn(root, params, info):
    conditional = attrsGroups["conditionalProcessing"]

    def enter(node):
        for attr_name, value in list(node.attributes.items()):
            if value == "" and attr_name not in conditional:
                del node.attributes[attr_name]

    return {"element": {"enter": lambda node, parent_node: enter(node)}}
