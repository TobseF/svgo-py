name = "convertEllipseToCircle"
description = "converts non-eccentric <ellipse>s to <circle>s"


def fn(root, params, info):
    def enter(node):
        if node.name == "ellipse":
            rx = node.attributes.get("rx") or "0"
            ry = node.attributes.get("ry") or "0"
            if rx == ry or rx == "auto" or ry == "auto":
                node.name = "circle"
                radius = ry if rx == "auto" else rx
                node.attributes.pop("rx", None)
                node.attributes.pop("ry", None)
                node.attributes["r"] = radius

    return {"element": {"enter": lambda node, parent_node: enter(node)}}
