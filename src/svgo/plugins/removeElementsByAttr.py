from ..xast import detach_node_from_parent

name = "removeElementsByAttr"
description = "removes arbitrary elements by ID or className"


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def fn(root, params, info):
    ids = _as_list(params.get("id"))
    classes = _as_list(params.get("class"))

    def enter(node, parent_node):
        if node.attributes.get("id") is not None and len(ids) != 0:
            if node.attributes["id"] in ids:
                detach_node_from_parent(node, parent_node)
        if node.attributes.get("class") and len(classes) != 0:
            class_list = node.attributes["class"].split(" ")
            for item in classes:
                if item in class_list:
                    detach_node_from_parent(node, parent_node)
                    break

    return {"element": {"enter": enter}}
