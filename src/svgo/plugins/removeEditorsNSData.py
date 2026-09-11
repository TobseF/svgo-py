from ..collections import editorNamespaces
from ..xast import detach_node_from_parent

name = "removeEditorsNSData"
description = "removes editors namespaces, elements and attributes"


def fn(root, params, info):
    namespaces = set(editorNamespaces)
    additional = params.get("additionalNamespaces")
    if isinstance(additional, (list, tuple)):
        namespaces = set(editorNamespaces) | set(additional)
    prefixes = []

    def enter(node, parent_node):
        if node.name == "svg":
            for attr_name, value in list(node.attributes.items()):
                if attr_name.startswith("xmlns:") and value in namespaces:
                    prefixes.append(attr_name[len("xmlns:"):])
                    del node.attributes[attr_name]
        for attr_name in list(node.attributes.keys()):
            if ":" in attr_name:
                prefix = attr_name.split(":", 1)[0]
                if prefix in prefixes:
                    del node.attributes[attr_name]
        if ":" in node.name:
            prefix = node.name.split(":", 1)[0]
            if prefix in prefixes:
                detach_node_from_parent(node, parent_node)

    return {"element": {"enter": enter}}
