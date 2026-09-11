from ..collections import elemsGroups, inheritableAttrs
from ..style import collect_stylesheet, compute_style

name = "collapseGroups"
description = "collapses useless groups"

_animation = elemsGroups["animation"]


def _has_animated_attr(node, attr_name):
    if node.type == "element":
        if node.name in _animation and node.attributes.get("attributeName") == attr_name:
            return True
        for child in node.children:
            if _has_animated_attr(child, attr_name):
                return True
    return False


def fn(root, params, info):
    stylesheet = collect_stylesheet(root)

    def exit(node, parent_node):
        if parent_node.type == "root" or getattr(parent_node, "name", None) == "switch":
            return
        if node.name != "g" or len(node.children) == 0:
            return

        # move group attributes to the single child element
        if len(node.attributes) != 0 and len(node.children) == 1:
            first_child = node.children[0]
            node_has_filter = bool(
                node.attributes.get("filter") or compute_style(stylesheet, node).get("filter")
            )
            if (
                first_child.type == "element"
                and first_child.attributes.get("id") is None
                and not node_has_filter
                and (
                    node.attributes.get("class") is None
                    or first_child.attributes.get("class") is None
                )
                and (
                    (node.attributes.get("clip-path") is None and node.attributes.get("mask") is None)
                    or (
                        first_child.name == "g"
                        and node.attributes.get("transform") is None
                        and first_child.attributes.get("transform") is None
                    )
                )
            ):
                new_attrs = dict(first_child.attributes)
                for attr_name, value in node.attributes.items():
                    if _has_animated_attr(first_child, attr_name):
                        return
                    if new_attrs.get(attr_name) is None:
                        new_attrs[attr_name] = value
                    elif attr_name == "transform":
                        new_attrs[attr_name] = value + " " + new_attrs[attr_name]
                    elif new_attrs[attr_name] == "inherit":
                        new_attrs[attr_name] = value
                    elif attr_name not in inheritableAttrs and new_attrs[attr_name] != value:
                        return
                node.attributes = {}
                first_child.attributes = new_attrs

        # collapse groups without attributes
        if len(node.attributes) == 0:
            for child in node.children:
                if child.type == "element" and child.name in _animation:
                    return
            # replace current node with all its children (in place)
            index = next(i for i, c in enumerate(parent_node.children) if c is node)
            parent_node.children[index:index + 1] = node.children

    return {"element": {"exit": exit}}
