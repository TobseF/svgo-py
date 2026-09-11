from ..collections import (
    attrsGroups,
    inheritableAttrs,
    presentationNonInheritableGroupAttrs,
)

name = "removeNonInheritableGroupAttrs"
description = "removes non-inheritable group's presentational attributes"

_presentation = attrsGroups["presentation"]


def fn(root, params, info):
    def enter(node):
        if node.name == "g":
            for attr_name in list(node.attributes.keys()):
                if (
                    attr_name in _presentation
                    and attr_name not in inheritableAttrs
                    and attr_name not in presentationNonInheritableGroupAttrs
                ):
                    del node.attributes[attr_name]

    return {"element": {"enter": lambda node, parent_node: enter(node)}}
