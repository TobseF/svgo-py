from ..collections import pathElems, referencesProps
from ..tools import includes_url_reference

name = "moveGroupAttrsToElems"
description = "moves some group attributes to the content elements"

_path_elems_with_groups_and_text = set(pathElems) | {"g", "text"}


def fn(root, params, info):
    def enter(node):
        if (
            node.name == "g"
            and len(node.children) != 0
            and node.attributes.get("transform") is not None
            and not any(
                name in referencesProps and includes_url_reference(value)
                for name, value in node.attributes.items()
            )
            and all(
                child.type == "element"
                and child.name in _path_elems_with_groups_and_text
                and child.attributes.get("id") is None
                for child in node.children
            )
        ):
            value = node.attributes["transform"]
            for child in node.children:
                if child.type == "element":
                    if child.attributes.get("transform") is not None:
                        child.attributes["transform"] = f"{value} {child.attributes['transform']}"
                    else:
                        child.attributes["transform"] = value
            del node.attributes["transform"]

    return {"element": {"enter": lambda node, parent_node: enter(node)}}
