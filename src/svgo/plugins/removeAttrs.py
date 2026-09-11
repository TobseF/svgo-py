import re
import sys

name = "removeAttrs"
description = "removes specified attributes"

_DEFAULT_SEPARATOR = ":"


def fn(root, params, info):
    if "attrs" not in params or params.get("attrs") is None:
        print('Warning: The plugin "removeAttrs" requires the "attrs" parameter.', file=sys.stderr)
        return None

    elem_separator = params["elemSeparator"] if isinstance(params.get("elemSeparator"), str) else _DEFAULT_SEPARATOR
    preserve_current_color = params["preserveCurrentColor"] if isinstance(params.get("preserveCurrentColor"), bool) else False
    attrs = params["attrs"] if isinstance(params["attrs"], (list, tuple)) else [params["attrs"]]

    patterns = []
    for attr in attrs:
        pattern = attr
        if elem_separator not in pattern:
            pattern = elem_separator.join([".*", pattern, ".*"])
        elif len(pattern.split(elem_separator)) < 3:
            pattern = elem_separator.join([pattern, ".*"])
        parts = []
        for value in pattern.split(elem_separator):
            if value == "*":
                value = ".*"
            parts.append(re.compile("^" + value + "$", re.I))
        patterns.append(parts)

    def enter(node):
        for lst in patterns:
            if lst[0].search(node.name):
                for attr_name, value in list(node.attributes.items()):
                    val = value if value is not None else ""
                    is_current_color = val.lower() == "currentcolor"
                    is_fill_cc = preserve_current_color and attr_name == "fill" and is_current_color
                    is_stroke_cc = preserve_current_color and attr_name == "stroke" and is_current_color
                    if (
                        not is_fill_cc
                        and not is_stroke_cc
                        and lst[1].search(attr_name)
                        and lst[2].search(val)
                    ):
                        del node.attributes[attr_name]

    return {"element": {"enter": lambda node, parent_node: enter(node)}}
