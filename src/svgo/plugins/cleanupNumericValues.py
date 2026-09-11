import re

from ..tools import js_number_to_string, js_to_fixed, remove_leading_zero

name = "cleanupNumericValues"
description = 'rounds numeric values to the fixed precision, removes default "px" units'

_reg_numeric = re.compile(
    r"^([-+]?\d*\.?\d+([eE][-+]?\d+)?)(px|pt|pc|mm|cm|m|in|ft|em|ex|%)?$"
)
_reg_viewbox_split = re.compile(r"(?:\s,?|,)\s*")

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

    def enter(node):
        viewbox = node.attributes.get("viewBox")
        if viewbox is not None:
            numbers = _reg_viewbox_split.split(viewbox.strip())
            out = []
            for value in numbers:
                num = _to_number(value)
                if num != num:  # NaN
                    out.append(value)
                else:
                    out.append(js_number_to_string(js_to_fixed(num, float_precision)))
            node.attributes["viewBox"] = " ".join(out)

        for attr_name, value in list(node.attributes.items()):
            if attr_name == "version":
                continue
            match = _reg_numeric.match(value)
            if not match:
                continue
            num = js_to_fixed(_to_number(match.group(1)), float_precision)
            matched_unit = match.group(3) or ""
            units = matched_unit

            if convert_to_px and units != "" and units in _absolute_lengths:
                px_num = js_to_fixed(
                    _absolute_lengths[units] * _to_number(match.group(1)), float_precision
                )
                if len(js_number_to_string(px_num)) < len(match.group(0)):
                    num = px_num
                    units = "px"

            if leading_zero:
                s = remove_leading_zero(num)
            else:
                s = js_number_to_string(num)

            if default_px and units == "px":
                units = ""

            node.attributes[attr_name] = s + units

    return {"element": {"enter": lambda node, parent_node: enter(node)}}
