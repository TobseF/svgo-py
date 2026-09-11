from ..tools import js_number, js_number_to_string

name = "removeDimensions"
description = "removes width and height in presence of viewBox (opposite to removeViewBox)"


def _isnan(x):
    return x != x


def fn(root, params, info):
    def enter(node):
        if node.name != "svg":
            return
        if node.attributes.get("viewBox") is not None:
            node.attributes.pop("width", None)
            node.attributes.pop("height", None)
        elif (
            node.attributes.get("width") is not None
            and node.attributes.get("height") is not None
            and not _isnan(js_number(node.attributes["width"]))
            and not _isnan(js_number(node.attributes["height"]))
        ):
            width = js_number(node.attributes["width"])
            height = js_number(node.attributes["height"])
            node.attributes["viewBox"] = f"0 0 {js_number_to_string(width)} {js_number_to_string(height)}"
            node.attributes.pop("width", None)
            node.attributes.pop("height", None)

    return {"element": {"enter": lambda node, parent_node: enter(node)}}
