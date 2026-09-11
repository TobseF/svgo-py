import re

from ..xast import detach_node_from_parent

name = "removeRasterImages"
description = "removes raster images"

_reg = re.compile(r"(\.|image/)(jpe?g|png|gif)")


def fn(root, params, info):
    def enter(node, parent_node):
        href = node.attributes.get("xlink:href")
        if node.name == "image" and href is not None and _reg.search(href):
            detach_node_from_parent(node, parent_node)

    return {"element": {"enter": enter}}
