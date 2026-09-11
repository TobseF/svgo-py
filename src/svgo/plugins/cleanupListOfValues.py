import re

from ..tools import js_number_to_string, js_to_fixed, remove_leading_zero

name = "cleanupListOfValues"
description = "rounds list of values to the fixed precision"

_reg_numeric = re.compile(r"^([-+]?\d*\.?\d+([eE][-+]?\d+)?)(px|pt|pc|mm|cm|m|in|ft|em|ex|%)?$")
_reg_separator = re.compile(r"\s+,?\s*|,\s*")
_reg_new = re.compile(r"new")

_absolute_lengths = {
    "cm": 96 / 2.54,
    "mm": 96 / 25.4,
    "in": 96,
    "pt": 4 / 3,
    "pc": 16,
    "px": 1,
}


def _to_number(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return float("nan")


def fn(root, params, info):
    float_precision = params.get("floatPrecision", 3)
    leading_zero = params.get("leadingZero", True)
    default_px = params.get("defaultPx", True)
    convert_to_px = params.get("convertToPx", True)

    def round_values(lists):
        rounded = []
        for elem in _reg_separator.split(lists):
            match = _reg_numeric.match(elem)
            if match:
                num = js_to_fixed(_to_number(match.group(1)), float_precision)
                units = match.group(3) or ""
                if convert_to_px and units and units in _absolute_lengths:
                    px_num = js_to_fixed(_absolute_lengths[units] * _to_number(match.group(1)), float_precision)
                    if len(js_number_to_string(px_num)) < len(match.group(0)):
                        num = px_num
                        units = "px"
                s = remove_leading_zero(num) if leading_zero else js_number_to_string(num)
                if default_px and units == "px":
                    units = ""
                rounded.append(s + units)
            elif _reg_new.search(elem):
                rounded.append("new")
            elif elem:
                rounded.append(elem)
        return " ".join(rounded)

    def enter(node):
        for attr in ("points", "enable-background", "viewBox", "stroke-dasharray", "dx", "dy", "x", "y"):
            if node.attributes.get(attr) is not None:
                node.attributes[attr] = round_values(node.attributes[attr])

    return {"element": {"enter": lambda node, parent_node: enter(node)}}
