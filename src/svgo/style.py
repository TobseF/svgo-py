"""Computed-style helpers. Port of ``lib/style.js``.

A "stylesheet" snapshot bundles the CSS rules collected from ``<style>``
elements, a node->parent map, and a per-style-string declaration cache.
"""

from __future__ import annotations

import functools
from typing import Any, Dict, List, Optional

from . import css
from .collections import (
    attrsGroups,
    inheritableAttrs,
    presentationNonInheritableGroupAttrs,
)
from .visit import visit

_presentation = attrsGroups["presentation"]


class Stylesheet:
    __slots__ = ("rules", "parents", "declaration_cache")

    def __init__(self, rules, parents, declaration_cache):
        self.rules = rules
        self.parents = parents
        self.declaration_cache = declaration_cache


def compare_specificity(a, b) -> int:
    return css.compare_specificity(a, b)


def collect_stylesheet(root) -> Stylesheet:
    rules: List[css.Rule] = []
    parents: Dict[Any, Any] = {}

    def enter(node, parent_node):
        parents[node] = parent_node
        if node.name != "style":
            return
        type_attr = node.attributes.get("type")
        if type_attr is None or type_attr == "" or type_attr == "text/css":
            media = node.attributes.get("media")
            dynamic = media is not None and media != "all"
            for child in node.children:
                if child.type in ("text", "cdata"):
                    rules.extend(css.parse_stylesheet(child.value, dynamic))

    visit(root, {"element": {"enter": enter}})

    # stable sort by specificity (ascending) -- later + more specific wins
    rules.sort(key=functools.cmp_to_key(lambda a, b: css.compare_specificity(a.specificity, b.specificity)))
    return Stylesheet(rules, parents, {})


def _compute_own_style(stylesheet: Stylesheet, node, parents) -> Dict[str, Dict[str, Any]]:
    computed_style: Dict[str, Dict[str, Any]] = {}
    important_styles: Dict[str, bool] = {}

    # collect presentation attributes
    for name, value in node.attributes.items():
        if name in _presentation:
            computed_style[name] = {"type": "static", "inherited": False, "value": value}
            important_styles[name] = False

    # collect matching rules
    for rule in stylesheet.rules:
        if css.matches(node, rule.selector, parents):
            for decl in rule.declarations:
                name = decl.name
                computed = computed_style.get(name)
                if computed and computed["type"] == "dynamic":
                    continue
                if rule.dynamic:
                    computed_style[name] = {"type": "dynamic", "inherited": False}
                    continue
                if (
                    computed is None
                    or decl.important is True
                    or important_styles.get(name) is False
                ):
                    computed_style[name] = {"type": "static", "inherited": False, "value": decl.value}
                    important_styles[name] = decl.important

    # collect inline styles
    style_declarations: List[css.Declaration] = []
    style_attr = node.attributes.get("style")
    if style_attr is not None:
        cached = stylesheet.declaration_cache.get(style_attr)
        if cached is None:
            style_declarations = css.parse_style_declarations(style_attr)
            stylesheet.declaration_cache[style_attr] = style_declarations
        else:
            style_declarations = cached
    for decl in style_declarations:
        name = decl.name
        computed = computed_style.get(name)
        if computed and computed["type"] == "dynamic":
            continue
        if (
            computed is None
            or decl.important is True
            or important_styles.get(name) is False
        ):
            computed_style[name] = {"type": "static", "inherited": False, "value": decl.value}
            important_styles[name] = decl.important

    return computed_style


def compute_style(stylesheet: Stylesheet, node) -> Dict[str, Dict[str, Any]]:
    parents = stylesheet.parents
    computed_styles = _compute_own_style(stylesheet, node, parents)
    parent = parents.get(node)
    while parent is not None and getattr(parent, "type", None) != "root":
        inherited_styles = _compute_own_style(stylesheet, parent, parents)
        for name, computed in inherited_styles.items():
            if (
                computed_styles.get(name) is None
                and name in inheritableAttrs
                and name not in presentationNonInheritableGroupAttrs
            ):
                inherited = dict(computed)
                inherited["inherited"] = True
                computed_styles[name] = inherited
        parent = parents.get(parent)
    return computed_styles


def includes_attr_selector(selector, name: str, value: Optional[str] = None, traversed: bool = False) -> bool:
    """Whether a CSS selector includes/traverses the given attribute.

    Classes and ids are represented as attribute selectors ``class`` / ``id``.
    Mirrors ``lib/style.js`` includesAttrSelector, which flattens each complex
    selector into ordered segments (css-what style) with explicit traversal
    (combinator) markers.
    """
    from cssselect import parse as _parse

    if not isinstance(selector, str):
        selector = str(selector)

    try:
        parsed = _parse(selector)
    except Exception:
        return False

    for sel in parsed:
        segments = _flatten(sel.parsed_tree)
        n = len(segments)
        for index, segment in enumerate(segments):
            if traversed:
                if index == n - 1:
                    continue
                if segments[index + 1].get("type") != "combinator":
                    continue
            if segment.get("type") != "attribute" or segment.get("name") != name:
                continue
            if value is None or segment.get("value") == value:
                return True
    return False


def _flatten(tree) -> List[Dict[str, Any]]:
    """Flatten a cssselect complex-selector tree into an ordered segment list
    with explicit ``combinator`` markers between compounds (source order)."""
    from cssselect.parser import Attrib, Class, Hash, CombinedSelector

    segments: List[Dict[str, Any]] = []

    def walk(node):
        if isinstance(node, CombinedSelector):
            walk(node.selector)
            segments.append({"type": "combinator"})
            walk(node.subselector)
            return
        sub = getattr(node, "selector", None)
        if sub is not None:
            walk(sub)
        if isinstance(node, Class):
            segments.append({"type": "attribute", "name": "class", "value": node.class_name})
        elif isinstance(node, Hash):
            segments.append({"type": "attribute", "name": "id", "value": node.id})
        elif isinstance(node, Attrib):
            val = node.value.value if hasattr(node.value, "value") else node.value
            segments.append({"type": "attribute", "name": node.attrib, "value": val})

    walk(tree)
    return segments
