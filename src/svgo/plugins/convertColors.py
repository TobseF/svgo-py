import math
import re

from ..collections import colorsNames, colorsProps, colorsShortNames
from ..tools import includes_css_var_reference, includes_url_reference

name = "convertColors"
description = "converts colors: rgb() to #rrggbb and #rrggbb to #rgb"

_rNumber = r"([+-]?(?:\d*\.\d+|\d+\.?)%?)"
_rComma = r"(?:\s*,\s*|\s+)"
_regRGB = re.compile(r"^rgb\(\s*" + _rNumber + _rComma + _rNumber + _rComma + _rNumber + r"\s*\)$")
_regHEX = re.compile(r"^#(([a-fA-F0-9])\2){3}$")


def _convert_rgb_to_hex(r, g, b):
    # truncate toward zero (JS bitwise ToInt32) then pack
    r, g, b = int(r), int(g), int(b)
    hex_number = ((((256 + r) << 8) | g) << 8) | b
    return "#" + format(hex_number, "x")[1:].upper()


def fn(root, params, info):
    current_color = params.get("currentColor", False)
    names2hex = params.get("names2hex", True)
    rgb2hex = params.get("rgb2hex", True)
    convert_case = params.get("convertCase", "lower")
    shorthex = params.get("shorthex", True)
    shortname = params.get("shortname", True)

    mask_counter = [0]

    def enter(node):
        if node.name == "mask":
            mask_counter[0] += 1
        for attr_name, value in list(node.attributes.items()):
            if attr_name not in colorsProps:
                continue
            val = value

            if current_color and mask_counter[0] == 0:
                if isinstance(current_color, str):
                    matched = val == current_color
                elif hasattr(current_color, "search"):  # compiled regex
                    matched = current_color.search(val) is not None
                else:
                    matched = val != "none"
                if matched:
                    val = "currentColor"

            if names2hex:
                color_name = val.lower()
                if colorsNames.get(color_name) is not None:
                    val = colorsNames[color_name]

            if rgb2hex:
                match = _regRGB.match(val)
                if match is not None:
                    numbers = []
                    for m in match.groups()[:3]:
                        if "%" in m:
                            n = math.floor(float(m.replace("%", "")) * 2.55 + 0.5)
                        else:
                            n = float(m)
                        numbers.append(max(0, min(n, 255)))
                    val = _convert_rgb_to_hex(*numbers)

            if (
                convert_case
                and not includes_url_reference(val)
                and not includes_css_var_reference(val)
                and val != "currentColor"
            ):
                if convert_case == "lower":
                    val = val.lower()
                elif convert_case == "upper":
                    val = val.upper()

            if shorthex:
                match = _regHEX.match(val)
                if match is not None:
                    whole = match.group(0)
                    val = "#" + whole[1] + whole[3] + whole[5]

            if shortname:
                color_name = val.lower()
                if colorsShortNames.get(color_name) is not None:
                    val = colorsShortNames[color_name]

            node.attributes[attr_name] = val

    def exit(node):
        if node.name == "mask":
            mask_counter[0] -= 1

    return {
        "element": {
            "enter": lambda node, parent_node: enter(node),
            "exit": lambda node, parent_node: exit(node),
        }
    }
