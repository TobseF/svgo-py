import functools

name = "sortAttrs"
description = "Sort element attributes for better compression"

_DEFAULT_ORDER = [
    "id", "width", "height", "x", "x1", "x2", "y", "y1", "y2",
    "cx", "cy", "r", "fill", "stroke", "marker", "d", "points",
]


def fn(root, params, info):
    order = params.get("order", _DEFAULT_ORDER)
    xmlns_order = params.get("xmlnsOrder", "front")

    def get_ns_priority(nm):
        if xmlns_order == "front":
            if nm == "xmlns":
                return 3
            if nm.startswith("xmlns:"):
                return 2
        if ":" in nm:
            return 1
        return 0

    def compare_attrs(a, b):
        a_name = a[0]
        b_name = b[0]
        a_priority = get_ns_priority(a_name)
        b_priority = get_ns_priority(b_name)
        priority_ns = b_priority - a_priority
        if priority_ns != 0:
            return priority_ns
        a_part = a_name.split("-", 1)[0]
        b_part = b_name.split("-", 1)[0]
        if a_part != b_part:
            a_in = 1 if a_part in order else 0
            b_in = 1 if b_part in order else 0
            if a_in == 1 and b_in == 1:
                return order.index(a_part) - order.index(b_part)
            priority_order = b_in - a_in
            if priority_order != 0:
                return priority_order
        return -1 if a_name < b_name else 1

    def enter(node):
        attrs = list(node.attributes.items())
        attrs.sort(key=functools.cmp_to_key(compare_attrs))
        node.attributes = {name_: value for name_, value in attrs}

    return {"element": {"enter": lambda node, parent_node: enter(node)}}
