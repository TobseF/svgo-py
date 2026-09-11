from ..collections import attrsGroupsDefaults, colorsProps
from ..css import query_selector, query_selector_all
from ..style import collect_stylesheet, compute_style
from ..xast import detach_node_from_parent

name = "convertOneStopGradients"
description = "converts one-stop (single color) gradients to a plain color"


def fn(root, params, info):
    stylesheet = collect_stylesheet(root)
    effected_defs = set()
    all_defs = {}
    gradients_to_detach = {}
    state = {"xlink_count": 0}

    def enter(node, parent_node):
        if node.attributes.get("xlink:href") is not None:
            state["xlink_count"] += 1

        if node.name == "defs":
            all_defs[node] = parent_node
            return

        if node.name not in ("linearGradient", "radialGradient"):
            return

        stops = [c for c in node.children if c.type == "element" and c.name == "stop"]
        href = node.attributes.get("xlink:href") or node.attributes.get("href")
        if len(stops) == 0 and href is not None and href.startswith("#"):
            effective_node = query_selector(root, _id_selector(href), strict=True)
        else:
            effective_node = node

        if effective_node is None or effective_node.type != "element":
            gradients_to_detach[node] = parent_node
            return

        effective_stops = [c for c in effective_node.children if c.type == "element" and c.name == "stop"]
        if len(effective_stops) != 1 or effective_stops[0].type != "element":
            return

        if parent_node.type == "element" and parent_node.name == "defs":
            effected_defs.add(parent_node)

        gradients_to_detach[node] = parent_node

        color = None
        style = compute_style(stylesheet, effective_stops[0]).get("stop-color")
        if style is not None and style["type"] == "static":
            color = style.get("value")

        selector_val = f"url(#{node.attributes.get('id')})"
        selector = ",".join(f'[{attr}="{selector_val}"]' for attr in colorsProps)
        try:
            elements = query_selector_all(root, selector, strict=True)
        except Exception:
            elements = []
        for element in elements:
            if element.type != "element":
                continue
            for attr in colorsProps:
                if element.attributes.get(attr) != selector_val:
                    continue
                if color is not None:
                    element.attributes[attr] = color
                else:
                    element.attributes.pop(attr, None)

        # elements whose style attribute references the gradient
        styled_elements = _find_style_referencing(root, selector_val)
        for element in styled_elements:
            element.attributes["style"] = element.attributes["style"].replace(
                selector_val, color or attrsGroupsDefaults["presentation"]["stop-color"]
            )

    def exit(node):
        if node.name == "svg":
            for gradient, parent in gradients_to_detach.items():
                if gradient.attributes.get("xlink:href") is not None:
                    state["xlink_count"] -= 1
                detach_node_from_parent(gradient, parent)
            if state["xlink_count"] == 0:
                node.attributes.pop("xmlns:xlink", None)
            for defs, parent in all_defs.items():
                if defs in effected_defs and len(defs.children) == 0:
                    detach_node_from_parent(defs, parent)

    return {"element": {"enter": enter, "exit": lambda node, parent_node: exit(node)}}


def _id_selector(href):
    # href like "#foo" -> selector "#foo"
    return href


def _find_style_referencing(root, selector_val):
    """Equivalent of querySelectorAll(root, `[style*=<val>]`) -- match elements
    whose style attribute contains the substring."""
    results = []

    def walk(n):
        for child in n.children:
            if child.type == "element":
                style = child.attributes.get("style")
                if style is not None and selector_val in style:
                    results.append(child)
                walk(child)

    walk(root)
    return results
