from ..collections import elemsGroups
from ..style import collect_stylesheet, compute_style
from ..tools import has_scripts
from ..visit import VISIT_SKIP, visit
from ..xast import detach_node_from_parent

name = "removeUselessStrokeAndFill"
description = "removes useless stroke and fill attributes"

_shape = elemsGroups["shape"]


def fn(root, params, info):
    remove_stroke = params.get("stroke", True)
    remove_fill = params.get("fill", True)
    remove_none = params.get("removeNone", False)

    has_style_or_script = [False]

    def check(node):
        if node.name == "style" or has_scripts(node):
            has_style_or_script[0] = True

    visit(root, {"element": {"enter": lambda node, parent: check(node)}})
    if has_style_or_script[0]:
        return None

    stylesheet = collect_stylesheet(root)

    def enter(node, parent_node):
        if node.attributes.get("id") is not None:
            return VISIT_SKIP
        if node.name not in _shape:
            return

        computed = compute_style(stylesheet, node)
        stroke = computed.get("stroke")
        stroke_opacity = computed.get("stroke-opacity")
        stroke_width = computed.get("stroke-width")
        marker_end = computed.get("marker-end")
        fill = computed.get("fill")
        fill_opacity = computed.get("fill-opacity")
        computed_parent = compute_style(stylesheet, parent_node) if parent_node.type == "element" else None
        parent_stroke = None if computed_parent is None else computed_parent.get("stroke")

        if remove_stroke:
            if (
                stroke is None
                or (stroke["type"] == "static" and stroke.get("value") == "none")
                or (stroke_opacity is not None and stroke_opacity["type"] == "static" and stroke_opacity.get("value") == "0")
                or (stroke_width is not None and stroke_width["type"] == "static" and stroke_width.get("value") == "0")
            ):
                if (
                    stroke_width is not None
                    and stroke_width["type"] == "static"
                    and stroke_width.get("value") == "0"
                ) or marker_end is None:
                    for attr_name in list(node.attributes.keys()):
                        if attr_name.startswith("stroke"):
                            del node.attributes[attr_name]
                    if parent_stroke is not None and parent_stroke["type"] == "static" and parent_stroke.get("value") != "none":
                        node.attributes["stroke"] = "none"

        if remove_fill:
            if (
                (fill is not None and fill["type"] == "static" and fill.get("value") == "none")
                or (fill_opacity is not None and fill_opacity["type"] == "static" and fill_opacity.get("value") == "0")
            ):
                for attr_name in list(node.attributes.keys()):
                    if attr_name.startswith("fill-"):
                        del node.attributes[attr_name]
                if fill is None or (fill["type"] == "static" and fill.get("value") != "none"):
                    node.attributes["fill"] = "none"

        if remove_none:
            if (
                (stroke is None or node.attributes.get("stroke") == "none")
                and (
                    (fill is not None and fill["type"] == "static" and fill.get("value") == "none")
                    or node.attributes.get("fill") == "none"
                )
            ):
                detach_node_from_parent(node, parent_node)

    return {"element": {"enter": enter}}
