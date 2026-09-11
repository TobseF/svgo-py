import re

from ..collections import (
    attrsGroups,
    attrsGroupsDefaults,
    elems,
    elemsGroups,
    presentationNonInheritableGroupAttrs,
)
from ..style import collect_stylesheet, compute_style, includes_attr_selector
from ..visit import VISIT_SKIP
from ..xast import detach_node_from_parent

name = "removeUnknownsAndDefaults"
description = "removes unknown elements content and attributes, removes attrs with default values"

# resolve all group references once
_allowed_children = {}
_allowed_attributes = {}
_attributes_defaults = {}

for _name, _config in elems.items():
    _children = set()
    for _el in _config.get("content") or []:
        _children.add(_el)
    for _group_name in _config.get("contentGroups") or []:
        _group = elemsGroups.get(_group_name)
        if _group:
            _children.update(_group)
    _attrs = set()
    for _attr in _config.get("attrs") or []:
        _attrs.add(_attr)
    _defaults = {}
    for _attr, _val in (_config.get("defaults") or {}).items():
        _defaults[_attr] = _val
    for _group_name in _config["attrsGroups"]:
        _group = attrsGroups.get(_group_name)
        if _group:
            _attrs.update(_group)
        _group_defaults = attrsGroupsDefaults.get(_group_name)
        if _group_defaults:
            for _attr, _val in _group_defaults.items():
                _defaults[_attr] = _val
    _allowed_children[_name] = _children
    _allowed_attributes[_name] = _attrs
    _attributes_defaults[_name] = _defaults

_reg_standalone = re.compile(r"\s*standalone\s*=\s*([\"'])no\1")


def fn(root, params, info):
    unknown_content = params.get("unknownContent", True)
    unknown_attrs = params.get("unknownAttrs", True)
    default_attrs = params.get("defaultAttrs", True)
    default_markup_declarations = params.get("defaultMarkupDeclarations", True)
    useless_overrides = params.get("uselessOverrides", True)
    keep_data_attrs = params.get("keepDataAttrs", True)
    keep_aria_attrs = params.get("keepAriaAttrs", True)
    keep_role_attr = params.get("keepRoleAttr", False)

    stylesheet = collect_stylesheet(root)

    def instruction_enter(node, parent_node):
        if default_markup_declarations:
            node.value = _reg_standalone.sub("", node.value)

    def element_enter(node, parent_node):
        if ":" in node.name:
            return
        if node.name == "foreignObject":
            return VISIT_SKIP

        if unknown_content and parent_node.type == "element":
            allowed = _allowed_children.get(parent_node.name)
            if allowed is None or len(allowed) == 0:
                if _allowed_children.get(node.name) is None:
                    detach_node_from_parent(node, parent_node)
                    return
            else:
                if node.name not in allowed:
                    detach_node_from_parent(node, parent_node)
                    return

        allowed_attributes = _allowed_attributes.get(node.name)
        attributes_defaults = _attributes_defaults.get(node.name)
        computed_parent_style = (
            compute_style(stylesheet, parent_node) if parent_node.type == "element" else None
        )

        for attr_name, value in list(node.attributes.items()):
            if keep_data_attrs and attr_name.startswith("data-"):
                continue
            if keep_aria_attrs and attr_name.startswith("aria-"):
                continue
            if keep_role_attr and attr_name == "role":
                continue
            if attr_name == "xmlns":
                continue
            if ":" in attr_name:
                prefix = attr_name.split(":", 1)[0]
                if prefix != "xml" and prefix != "xlink":
                    continue

            if unknown_attrs and allowed_attributes is not None and attr_name not in allowed_attributes:
                del node.attributes[attr_name]
                continue

            if (
                default_attrs
                and node.attributes.get("id") is None
                and attributes_defaults
                and attributes_defaults.get(attr_name) == value
            ):
                if (computed_parent_style is None or computed_parent_style.get(attr_name) is None) and not any(
                    includes_attr_selector(rule.selector, attr_name) for rule in stylesheet.rules
                ):
                    del node.attributes[attr_name]
                    continue

            if useless_overrides and node.attributes.get("id") is None:
                style = None if computed_parent_style is None else computed_parent_style.get(attr_name)
                if (
                    attr_name not in presentationNonInheritableGroupAttrs
                    and style is not None
                    and style["type"] == "static"
                    and style.get("value") == value
                ):
                    del node.attributes[attr_name]

    return {
        "instruction": {"enter": instruction_enter},
        "element": {"enter": element_enter},
    }
