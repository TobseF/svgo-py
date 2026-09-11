name = "removeUnusedNS"
description = "removes unused namespaces declaration"


def fn(root, params, info):
    unused_namespaces = set()

    def enter(node, parent_node):
        if node.name == "svg" and parent_node.type == "root":
            for attr_name in node.attributes.keys():
                if attr_name.startswith("xmlns:"):
                    unused_namespaces.add(attr_name[len("xmlns:"):])
        if len(unused_namespaces) != 0:
            if ":" in node.name:
                ns = node.name.split(":", 1)[0]
                unused_namespaces.discard(ns)
            for attr_name in node.attributes.keys():
                if ":" in attr_name:
                    ns = attr_name.split(":", 1)[0]
                    unused_namespaces.discard(ns)

    def exit(node, parent_node):
        if node.name == "svg" and parent_node.type == "root":
            for ns in unused_namespaces:
                node.attributes.pop(f"xmlns:{ns}", None)

    return {"element": {"enter": enter, "exit": exit}}
