import re

name = "removeViewBox"
description = "removes viewBox attribute when possible"

_viewbox_elems = {"pattern", "svg", "symbol"}
_split = re.compile(r"[ ,]+")
_px = re.compile(r"px$")


def fn(root, params, info):
    def enter(node, parent_node):
        if (
            node.name in _viewbox_elems
            and node.attributes.get("viewBox") is not None
            and node.attributes.get("width") is not None
            and node.attributes.get("height") is not None
        ):
            if node.name == "svg" and parent_node.type != "root":
                return
            numbers = _split.split(node.attributes["viewBox"])
            if (
                len(numbers) >= 4
                and numbers[0] == "0"
                and numbers[1] == "0"
                and _px.sub("", node.attributes["width"]) == numbers[2]
                and _px.sub("", node.attributes["height"]) == numbers[3]
            ):
                del node.attributes["viewBox"]

    return {"element": {"enter": enter}}
