import re

from ..path import parse_path_data
from ..pathutil import intersects
from ..visit import VISIT_SKIP
from ..xast import detach_node_from_parent

name = "removeOffCanvasPaths"
description = "removes elements that are drawn outside of the viewBox"

_reg_clean = re.compile(r"[,+]|px")
_reg_ws = re.compile(r"\s+")
_reg_vb = re.compile(r"^(-?\d*\.?\d+) (-?\d*\.?\d+) (\d*\.?\d+) (\d*\.?\d+)$")


def fn(root, params, info):
    state = {"viewbox": None}

    def enter(node, parent_node):
        if node.name == "svg" and parent_node.type == "root":
            viewbox = ""
            if node.attributes.get("viewBox") is not None:
                viewbox = node.attributes["viewBox"]
            elif node.attributes.get("height") is not None and node.attributes.get("width") is not None:
                viewbox = f"0 0 {node.attributes['width']} {node.attributes['height']}"

            viewbox = _reg_clean.sub(" ", viewbox)
            viewbox = _reg_ws.sub(" ", viewbox)
            viewbox = viewbox.strip()
            m = _reg_vb.match(viewbox)
            if m is None:
                return
            left = float(m.group(1))
            top = float(m.group(2))
            width = float(m.group(3))
            height = float(m.group(4))
            state["viewbox"] = {
                "left": left,
                "top": top,
                "right": left + width,
                "bottom": top + height,
                "width": width,
                "height": height,
            }

        if node.attributes.get("transform") is not None:
            return VISIT_SKIP

        vb = state["viewbox"]
        if node.name == "path" and node.attributes.get("d") is not None and vb is not None:
            path_data = parse_path_data(node.attributes["d"])
            visible = False
            for item in path_data:
                if item["command"] == "M":
                    x, y = item["args"][0], item["args"][1]
                    if vb["left"] <= x <= vb["right"] and vb["top"] <= y <= vb["bottom"]:
                        visible = True
            if visible:
                return
            if len(path_data) == 2:
                path_data.append({"command": "z", "args": []})
            viewbox_path = [
                {"command": "M", "args": [vb["left"], vb["top"]]},
                {"command": "h", "args": [vb["width"]]},
                {"command": "v", "args": [vb["height"]]},
                {"command": "H", "args": [vb["left"]]},
                {"command": "z", "args": []},
            ]
            if intersects(viewbox_path, path_data) is False:
                detach_node_from_parent(node, parent_node)

    return {"element": {"enter": enter}}
