from ..collections import inheritableAttrs, pathElems
from ..visit import visit

name = "moveElemsAttrsToGroup"
description = "Move common attributes of group children to the group"


def fn(root, params, info):
    deoptimized = [False]

    def find_style(node):
        if node.name == "style":
            deoptimized[0] = True

    visit(root, {"element": {"enter": lambda node, parent: find_style(node)}})

    def exit(node):
        if node.name != "g" or len(node.children) <= 1:
            return
        if deoptimized[0]:
            return

        common = {}
        initial = True
        every_child_is_path = True
        for child in node.children:
            if child.type == "element":
                if child.name not in pathElems:
                    every_child_is_path = False
                if initial:
                    initial = False
                    for attr_name, value in child.attributes.items():
                        if attr_name in inheritableAttrs:
                            common[attr_name] = value
                else:
                    for attr_name in list(common.keys()):
                        if child.attributes.get(attr_name) != common[attr_name]:
                            del common[attr_name]

        if (
            node.attributes.get("filter") is not None
            or node.attributes.get("clip-path") is not None
            or node.attributes.get("mask") is not None
        ):
            common.pop("transform", None)

        if every_child_is_path:
            common.pop("transform", None)

        for attr_name, value in common.items():
            if attr_name == "transform":
                if node.attributes.get("transform") is not None:
                    node.attributes["transform"] = f"{node.attributes['transform']} {value}"
                else:
                    node.attributes["transform"] = value
            else:
                node.attributes[attr_name] = value

        for child in node.children:
            if child.type == "element":
                for attr_name in common.keys():
                    child.attributes.pop(attr_name, None)

    return {"element": {"exit": lambda node, parent_node: exit(node)}}
