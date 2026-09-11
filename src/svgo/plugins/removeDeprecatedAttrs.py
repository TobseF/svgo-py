from ..collections import attrsGroupsDeprecated, elems
from ..style import collect_stylesheet, _flatten

name = "removeDeprecatedAttrs"
description = "removes deprecated attributes"


def _extract_attributes_in_stylesheet(stylesheet):
    result = set()
    for rule in stylesheet.rules:
        try:
            from cssselect import parse as _parse

            for sel in _parse(rule.selector):
                for seg in _flatten(sel.parsed_tree):
                    if seg.get("type") == "attribute":
                        result.add(seg["name"])
        except Exception:
            continue
    return result


def _process_attributes(node, deprecated_attrs, remove_unsafe, attrs_in_stylesheet):
    if not deprecated_attrs:
        return
    safe = deprecated_attrs.get("safe")
    if safe:
        for nm in safe:
            if nm in attrs_in_stylesheet:
                continue
            node.attributes.pop(nm, None)
    unsafe = deprecated_attrs.get("unsafe")
    if remove_unsafe and unsafe:
        for nm in unsafe:
            if nm in attrs_in_stylesheet:
                continue
            node.attributes.pop(nm, None)


def fn(root, params, info):
    remove_unsafe = params.get("removeUnsafe", False)
    stylesheet = collect_stylesheet(root)
    attrs_in_stylesheet = _extract_attributes_in_stylesheet(stylesheet)

    def enter(node):
        elem_config = elems.get(node.name)
        if not elem_config:
            return

        if (
            "core" in elem_config["attrsGroups"]
            and node.attributes.get("xml:lang")
            and "xml:lang" not in attrs_in_stylesheet
            and node.attributes.get("lang")
        ):
            node.attributes.pop("xml:lang", None)

        for attrs_group in elem_config["attrsGroups"]:
            _process_attributes(
                node, attrsGroupsDeprecated.get(attrs_group), remove_unsafe, attrs_in_stylesheet
            )

        _process_attributes(
            node, elem_config.get("deprecated"), remove_unsafe, attrs_in_stylesheet
        )

    return {"element": {"enter": lambda node, parent_node: enter(node)}}
