import re

name = "cleanupAttrs"
description = "cleanups attributes from newlines, trailing and repeating spaces"

_reg_newlines_need_space = re.compile(r"(\S)\r?\n(\S)")
_reg_newlines = re.compile(r"\r?\n")
_reg_spaces = re.compile(r"\s{2,}")


def fn(root, params, info):
    newlines = params.get("newlines", True)
    trim = params.get("trim", True)
    spaces = params.get("spaces", True)

    def enter(node):
        for attr_name in list(node.attributes.keys()):
            value = node.attributes[attr_name]
            if newlines:
                value = _reg_newlines_need_space.sub(r"\1 \2", value)
                value = _reg_newlines.sub("", value)
            if trim:
                value = value.strip()
            if spaces:
                value = _reg_spaces.sub(" ", value)
            node.attributes[attr_name] = value

    return {"element": {"enter": lambda node, parent_node: enter(node)}}
