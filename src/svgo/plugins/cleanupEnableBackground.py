import re

from .. import css
from ..visit import visit

name = "cleanupEnableBackground"
description = "remove or cleanup enable-background attribute when possible"

_reg = re.compile(
    r"^new\s0\s0\s([-+]?\d*\.?\d+([eE][-+]?\d+)?)\s([-+]?\d*\.?\d+([eE][-+]?\d+)?)$"
)


def _serialize(declarations):
    parts = []
    for decl in declarations:
        important = "!important" if decl.important else ""
        parts.append(f"{decl.name}:{decl.value}{important}")
    return ";".join(parts)


def _cleanup_value(value, node_name, width, height):
    match = _reg.match(value)
    if match is not None and width == match.group(1) and height == match.group(3):
        return None if node_name == "svg" else "new"
    return value


def fn(root, params, info):
    has_filter = [False]

    def find_filter(node):
        if node.name == "filter":
            has_filter[0] = True

    visit(root, {"element": {"enter": lambda node, parent: find_filter(node)}})

    def enter(node):
        declarations = None
        eb_index = None  # index of enable-background declaration in `declarations`

        style_attr = node.attributes.get("style")
        if style_attr is not None:
            declarations = css.parse_style_declarations(style_attr)
            eb_positions = [i for i, d in enumerate(declarations) if d.name == "enable-background"]
            # remove all but the last enable-background declaration
            for i in eb_positions[:-1]:
                declarations[i] = None
            declarations = [d for d in declarations if d is not None]
            eb_positions = [i for i, d in enumerate(declarations) if d.name == "enable-background"]
            eb_index = eb_positions[-1] if eb_positions else None

        if not has_filter[0]:
            node.attributes.pop("enable-background", None)
            if declarations is not None:
                if eb_index is not None:
                    del declarations[eb_index]
                if not declarations:
                    node.attributes.pop("style", None)
                else:
                    node.attributes["style"] = _serialize(declarations)
            return

        has_dimensions = (
            node.attributes.get("width") is not None
            and node.attributes.get("height") is not None
        )
        if node.name in ("svg", "mask", "pattern") and has_dimensions:
            attr_value = node.attributes.get("enable-background")
            if attr_value is not None:
                attr_cleaned = _cleanup_value(
                    attr_value, node.name, node.attributes["width"], node.attributes["height"]
                )
                if attr_cleaned:
                    node.attributes["enable-background"] = attr_cleaned
                else:
                    node.attributes.pop("enable-background", None)

            if declarations is not None and eb_index is not None:
                style_value = declarations[eb_index].value
                style_cleaned = _cleanup_value(
                    style_value, node.name, node.attributes.get("width"), node.attributes.get("height")
                )
                if style_cleaned:
                    declarations[eb_index].value = style_cleaned
                else:
                    del declarations[eb_index]

        if declarations is not None:
            if not declarations:
                node.attributes.pop("style", None)
            else:
                node.attributes["style"] = _serialize(declarations)

    return {"element": {"enter": lambda node, parent_node: enter(node)}}
