import math
import re

from ..path import stringify_path_data
from ..tools import js_number
from ..xast import detach_node_from_parent

name = "convertShapeToPath"
description = "converts basic shapes to more compact path form"

_reg_number = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def _isnan(x):
    return x != x


def fn(root, params, info):
    convert_arcs = params.get("convertArcs", False)
    precision = params.get("floatPrecision")

    def enter(node, parent_node):
        attrs = node.attributes

        # rect -> path
        if (
            node.name == "rect"
            and attrs.get("width") is not None
            and attrs.get("height") is not None
            and attrs.get("rx") is None
            and attrs.get("ry") is None
        ):
            x = js_number(attrs.get("x") or "0")
            y = js_number(attrs.get("y") or "0")
            width = js_number(attrs["width"])
            height = js_number(attrs["height"])
            if _isnan(x - y + width - height):
                return
            path_data = [
                {"command": "M", "args": [x, y]},
                {"command": "H", "args": [x + width]},
                {"command": "V", "args": [y + height]},
                {"command": "H", "args": [x]},
                {"command": "z", "args": []},
            ]
            node.name = "path"
            attrs["d"] = stringify_path_data(path_data, precision=precision)
            for a in ("x", "y", "width", "height"):
                attrs.pop(a, None)

        # line -> path
        if node.name == "line":
            x1 = js_number(attrs.get("x1") or "0")
            y1 = js_number(attrs.get("y1") or "0")
            x2 = js_number(attrs.get("x2") or "0")
            y2 = js_number(attrs.get("y2") or "0")
            if _isnan(x1 - y1 + x2 - y2):
                return
            path_data = [
                {"command": "M", "args": [x1, y1]},
                {"command": "L", "args": [x2, y2]},
            ]
            node.name = "path"
            attrs["d"] = stringify_path_data(path_data, precision=precision)
            for a in ("x1", "y1", "x2", "y2"):
                attrs.pop(a, None)

        # polyline / polygon -> path
        if node.name in ("polyline", "polygon") and attrs.get("points") is not None:
            coords = [js_number(m) for m in _reg_number.findall(attrs["points"])]
            if len(coords) < 4:
                detach_node_from_parent(node, parent_node)
                return
            path_data = []
            for i in range(0, len(coords), 2):
                path_data.append(
                    {"command": "M" if i == 0 else "L", "args": coords[i:i + 2]}
                )
            if node.name == "polygon":
                path_data.append({"command": "z", "args": []})
            node.name = "path"
            attrs["d"] = stringify_path_data(path_data, precision=precision)
            attrs.pop("points", None)

        # circle -> path (optional)
        if node.name == "circle" and convert_arcs:
            cx = js_number(attrs.get("cx") or "0")
            cy = js_number(attrs.get("cy") or "0")
            r = js_number(attrs.get("r") or "0")
            if _isnan(cx - cy + r):
                return
            path_data = [
                {"command": "M", "args": [cx, cy - r]},
                {"command": "A", "args": [r, r, 0, 1, 0, cx, cy + r]},
                {"command": "A", "args": [r, r, 0, 1, 0, cx, cy - r]},
                {"command": "z", "args": []},
            ]
            node.name = "path"
            attrs["d"] = stringify_path_data(path_data, precision=precision)
            for a in ("cx", "cy", "r"):
                attrs.pop(a, None)

        # ellipse -> path (optional)
        if node.name == "ellipse" and convert_arcs:
            ecx = js_number(attrs.get("cx") or "0")
            ecy = js_number(attrs.get("cy") or "0")
            rx = js_number(attrs.get("rx") or "0")
            ry = js_number(attrs.get("ry") or "0")
            if _isnan(ecx - ecy + rx - ry):
                return
            path_data = [
                {"command": "M", "args": [ecx, ecy - ry]},
                {"command": "A", "args": [rx, ry, 0, 1, 0, ecx, ecy + ry]},
                {"command": "A", "args": [rx, ry, 0, 1, 0, ecx, ecy - ry]},
                {"command": "z", "args": []},
            ]
            node.name = "path"
            attrs["d"] = stringify_path_data(path_data, precision=precision)
            for a in ("cx", "cy", "rx", "ry"):
                attrs.pop(a, None)

    return {"element": {"enter": enter}}
