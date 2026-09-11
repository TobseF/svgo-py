"""CSS parsing, selector matching and specificity.

Replaces SVGO's use of ``css-tree`` (parsing), ``css-select`` (matching) and
``csso``/``css-what`` (specificity, selector introspection) with pure-Python
equivalents built on ``tinycss2`` and ``cssselect``.

Matching is implemented directly against the XAST node model. Pseudo-classes
are treated transparently -- exactly mirroring SVGO, which strips
``PseudoClassSelector`` nodes from a selector before matching and instead marks
the rule ``dynamic``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import tinycss2
from cssselect import parse as _cssselect_parse
from cssselect.parser import (
    Attrib,
    Class,
    CombinedSelector,
    Element,
    Function,
    Hash,
    Negation,
    Pseudo,
    SelectorSyntaxError,
)

try:  # newer cssselect exposes these too
    from cssselect.parser import Matching, Relation, SpecificityAdjustment
except Exception:  # pragma: no cover
    Matching = Relation = SpecificityAdjustment = ()


class Declaration:
    __slots__ = ("name", "value", "important")

    def __init__(self, name: str, value: str, important: bool):
        self.name = name
        self.value = value
        self.important = important

    def __repr__(self):
        return f"Declaration({self.name!r}, {self.value!r}, important={self.important})"


class Rule:
    __slots__ = ("selector", "specificity", "dynamic", "declarations")

    def __init__(self, selector: str, specificity, dynamic: bool, declarations: List[Declaration]):
        self.selector = selector
        self.specificity = specificity
        self.dynamic = dynamic
        self.declarations = declarations


# --------------------------------------------------------------------------
# declaration parsing
# --------------------------------------------------------------------------

def _serialize_value(tokens) -> str:
    return tinycss2.serialize(tokens).strip()


def parse_style_declarations(css: str) -> List[Declaration]:
    declarations: List[Declaration] = []
    for decl in tinycss2.parse_declaration_list(css, skip_comments=True, skip_whitespace=True):
        if decl.type == "declaration":
            declarations.append(
                Declaration(decl.lower_name, _serialize_value(decl.value), bool(decl.important))
            )
    return declarations


# --------------------------------------------------------------------------
# stylesheet parsing
# --------------------------------------------------------------------------

_KEYFRAME_ATRULES = {"keyframes", "-webkit-keyframes", "-o-keyframes", "-moz-keyframes"}


def _rules_from_qualified(rule, dynamic: bool) -> List[Rule]:
    prelude = tinycss2.serialize(rule.prelude).strip()
    content = rule.content if rule.content is not None else []
    declarations = [
        Declaration(d.lower_name, _serialize_value(d.value), bool(d.important))
        for d in tinycss2.parse_declaration_list(content, skip_comments=True, skip_whitespace=True)
        if d.type == "declaration"
    ]

    rules: List[Rule] = []
    # a prelude may hold multiple comma-separated selectors
    for selector_str in _split_selector_list(prelude):
        selector_str = selector_str.strip()
        if not selector_str:
            continue
        try:
            parsed = _cssselect_parse(selector_str)
        except SelectorSyntaxError:
            continue
        for sel in parsed:
            has_pseudo = _has_pseudo_class(sel.parsed_tree) or bool(sel.pseudo_element)
            rules.append(
                Rule(
                    # the prelude was already split on commas, so this fragment
                    # is a single selector
                    selector=selector_str,
                    specificity=sel.specificity(),
                    dynamic=has_pseudo or dynamic,
                    declarations=declarations,
                )
            )
    return rules


def _split_selector_list(prelude: str) -> List[str]:
    """Split a selector list on commas that are not inside brackets/parens."""
    parts = []
    depth = 0
    quote = ""
    current = []
    for ch in prelude:
        if quote:
            current.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in ('"', "'"):
            quote = ch
            current.append(ch)
        elif ch in "([":
            depth += 1
            current.append(ch)
        elif ch in ")]":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def _tree_to_selector(sel) -> str:
    # For a multi-selector prelude we keep the individual selector's canonical
    # text; cssselect does not round-trip perfectly, so we approximate by
    # re-serializing via its repr-free canonical form. Fall back to the raw
    # split fragment (already handled by caller for the single case).
    return _canonical(sel.parsed_tree)


def parse_stylesheet(css: str, dynamic: bool) -> List[Rule]:
    rules: List[Rule] = []
    nodes = tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)
    for node in nodes:
        if node.type == "qualified-rule":
            rules.extend(_rules_from_qualified(node, dynamic or False))
        elif node.type == "at-rule":
            if node.lower_at_keyword in _KEYFRAME_ATRULES:
                continue
            # descend into nested rules (e.g. @media) marking them dynamic
            if node.content is not None:
                inner = tinycss2.parse_stylesheet(
                    tinycss2.serialize(node.content), skip_comments=True, skip_whitespace=True
                )
                for inner_node in inner:
                    if inner_node.type == "qualified-rule":
                        rules.extend(_rules_from_qualified(inner_node, True))
    return rules


# --------------------------------------------------------------------------
# selector matching
# --------------------------------------------------------------------------

def _has_pseudo_class(tree) -> bool:
    if isinstance(tree, (Pseudo, Function)):
        return True
    if Negation and isinstance(tree, Negation):
        return True
    if Matching and isinstance(tree, Matching):
        return True
    if Relation and isinstance(tree, Relation):
        return True
    if SpecificityAdjustment and isinstance(tree, SpecificityAdjustment):
        return True
    sub = getattr(tree, "selector", None)
    if sub is not None and _has_pseudo_class(sub):
        return True
    sub2 = getattr(tree, "subselector", None)
    if sub2 is not None and _has_pseudo_class(sub2):
        return True
    return False


def _local_name(name: str) -> str:
    return name


def _get_classes(node) -> List[str]:
    cls = node.attributes.get("class")
    if not cls:
        return []
    return cls.split()


def _attr_matches(node, tree: "Attrib") -> bool:
    attr = tree.attrib
    op = tree.operator
    val = tree.value.value if hasattr(tree.value, "value") else tree.value
    actual = node.attributes.get(attr)
    if op == "exists":
        return actual is not None
    if actual is None:
        return False
    if op == "=":
        return actual == val
    if op == "~=":
        return val in actual.split()
    if op == "|=":
        return actual == val or actual.startswith(val + "-")
    if op == "^=":
        return bool(val) and actual.startswith(val)
    if op == "$=":
        return bool(val) and actual.endswith(val)
    if op == "*=":
        return bool(val) and val in actual
    if op == "!=":
        return actual != val
    return False


def _element_siblings(parent) -> List:
    if parent is None:
        return []
    return [c for c in parent.children if c.type == "element"]


# Pseudo-classes evaluated by the client only; in strict mode they never match.
_DYNAMIC_PSEUDOS = {
    "hover", "focus", "active", "visited", "link", "target", "focus-within",
    "focus-visible", "any-link", "checked", "disabled", "enabled", "required",
    "optional", "read-only", "read-write", "default", "valid", "invalid",
    "in-range", "out-of-range", "placeholder-shown", "autofill", "playing",
    "paused", "current", "past", "future",
}


def _structural_pseudo(node, ident, parents) -> bool:
    parent = parents.get(node)
    siblings = _element_siblings(parent)
    idx = _index_of(siblings, node)
    if ident == "root":
        return parent is None or getattr(parent, "type", None) == "root"
    if ident == "empty":
        return len(node.children) == 0
    if ident == "first-child":
        return idx == 0
    if ident == "last-child":
        return idx == len(siblings) - 1
    if ident == "only-child":
        return len(siblings) == 1
    if ident == "first-of-type":
        return _nth_of_type_index(siblings, node) == 0
    if ident == "last-of-type":
        same = [s for s in siblings if s.name == node.name]
        return same and same[-1] is node
    if ident == "only-of-type":
        same = [s for s in siblings if s.name == node.name]
        return len(same) == 1
    return False


def _nth_of_type_index(siblings, node) -> int:
    count = 0
    for s in siblings:
        if s.name == node.name:
            if s is node:
                return count
            count += 1
    return -1


def _nth_matches(expr, index_one_based) -> bool:
    expr = expr.strip().lower()
    if expr == "odd":
        a, b = 2, 1
    elif expr == "even":
        a, b = 2, 0
    else:
        import re as _re

        m = _re.match(r"^([+-]?\d*)n\s*([+-]\s*\d+)?$", expr.replace(" ", ""))
        if m:
            a_str = m.group(1)
            if a_str in ("", "+"):
                a = 1
            elif a_str == "-":
                a = -1
            else:
                a = int(a_str)
            b = int(m.group(2).replace(" ", "")) if m.group(2) else 0
        else:
            try:
                a, b = 0, int(expr)
            except ValueError:
                return False
    if a == 0:
        return index_one_based == b
    n = (index_one_based - b) / a
    return n >= 0 and n == int(n)


def _match(tree, node, parents: Dict[Any, Any], strict: bool = False) -> bool:
    if node is None or getattr(node, "type", None) != "element":
        return False

    if isinstance(tree, Element):
        el = tree.element
        return el is None or el == "*" or el == _local_name(node.name)

    if isinstance(tree, Hash):
        return node.attributes.get("id") == tree.id and _match(tree.selector, node, parents, strict)

    if isinstance(tree, Class):
        return tree.class_name in _get_classes(node) and _match(tree.selector, node, parents, strict)

    if isinstance(tree, Attrib):
        return _attr_matches(node, tree) and _match(tree.selector, node, parents, strict)

    if isinstance(tree, Pseudo):
        if strict:
            ident = tree.ident.lower()
            if ident in _DYNAMIC_PSEUDOS:
                return False
            if ident in (
                "root", "empty", "first-child", "last-child", "only-child",
                "first-of-type", "last-of-type", "only-of-type",
            ):
                return _structural_pseudo(node, ident, parents) and _match(tree.selector, node, parents, strict)
            # unknown pseudo-class in strict mode: do not match
            return False
        return _match(tree.selector, node, parents, strict)

    if isinstance(tree, Function):
        name = tree.name.lower()
        if name == "not":
            try:
                inner = _cssselect_parse(_arguments_to_string(tree.arguments))
            except Exception:
                return _match(tree.selector, node, parents, strict)
            neg = any(_match(s.parsed_tree, node, parents, strict) for s in inner)
            return (not neg) and _match(tree.selector, node, parents, strict)
        if strict and name in ("nth-child", "nth-last-child", "nth-of-type", "nth-last-of-type"):
            expr = _arguments_to_string(tree.arguments)
            parent = parents.get(node)
            siblings = _element_siblings(parent)
            if name == "nth-child":
                idx = _index_of(siblings, node) + 1
            elif name == "nth-last-child":
                idx = len(siblings) - _index_of(siblings, node)
            elif name == "nth-of-type":
                idx = _nth_of_type_index(siblings, node) + 1
            else:
                same = [s for s in siblings if s.name == node.name]
                idx = len(same) - _index_of(same, node)
            return _nth_matches(expr, idx) and _match(tree.selector, node, parents, strict)
        if strict:
            return False
        return _match(tree.selector, node, parents, strict)

    if Negation and isinstance(tree, Negation):
        neg = _match(tree.subselector, node, parents, strict)
        return (not neg) and _match(tree.selector, node, parents, strict)

    if isinstance(tree, CombinedSelector):
        if not _match(tree.subselector, node, parents, strict):
            return False
        combinator = tree.combinator
        parent = parents.get(node)
        if combinator == " ":
            anc = parents.get(node)
            while anc is not None and getattr(anc, "type", None) == "element":
                if _match(tree.selector, anc, parents, strict):
                    return True
                anc = parents.get(anc)
            return False
        if combinator == ">":
            return parent is not None and _match(tree.selector, parent, parents, strict)
        if combinator == "+":
            siblings = _element_siblings(parent)
            idx = _index_of(siblings, node)
            if idx > 0:
                return _match(tree.selector, siblings[idx - 1], parents, strict)
            return False
        if combinator == "~":
            siblings = _element_siblings(parent)
            idx = _index_of(siblings, node)
            for i in range(idx):
                if _match(tree.selector, siblings[i], parents, strict):
                    return True
            return False
        return False

    inner = getattr(tree, "selector", None)
    if inner is not None:
        return _match(inner, node, parents, strict)
    return False


def _index_of(seq, node) -> int:
    for i, item in enumerate(seq):
        if item is node:
            return i
    return -1


def _arguments_to_string(arguments) -> str:
    return tinycss2.serialize(arguments) if not isinstance(arguments, str) else arguments


def _canonical(tree) -> str:
    """Best-effort canonical selector text used for de-duplication only."""
    return repr(tree)


def matches(node, selector: str, parents: Optional[Dict[Any, Any]] = None, strict: bool = False) -> bool:
    if selector == "":
        return False
    if parents is None:
        parents = {}
    try:
        parsed = _cssselect_parse(selector)
    except SelectorSyntaxError:
        return False
    return any(_match(s.parsed_tree, node, parents, strict) for s in parsed)


def minify_css(css: str, preserve_exclamation: bool = True) -> str:
    """Best-effort CSS minifier (whitespace + comment removal).

    NOTE: this is *not* a full CSSO port. It performs whitespace/comment
    compaction only; it does not do CSSO's structural optimizations
    (shorthand merging, rule restructuring, usage-based dead-code removal).
    """
    out = []
    i = 0
    n = len(css)
    # characters around which surrounding whitespace can be dropped
    trim_around = set("{};:,>+~()")
    while i < n:
        ch = css[i]
        # comments
        if ch == "/" and i + 1 < n and css[i + 1] == "*":
            end = css.find("*/", i + 2)
            if end == -1:
                end = n - 2
            comment = css[i : end + 2]
            if preserve_exclamation and css[i + 2 : i + 3] == "!":
                out.append(comment)
            i = end + 2
            continue
        # strings
        if ch in ('"', "'"):
            j = i + 1
            while j < n and css[j] != ch:
                if css[j] == "\\":
                    j += 1
                j += 1
            out.append(css[i : j + 1])
            i = j + 1
            continue
        # url( ... ) unquoted
        if (ch in "uU") and css[i : i + 4].lower() == "url(":
            depth = 1
            j = i + 4
            while j < n and depth > 0:
                if css[j] in ('"', "'"):
                    q = css[j]
                    j += 1
                    while j < n and css[j] != q:
                        if css[j] == "\\":
                            j += 1
                        j += 1
                elif css[j] == "(":
                    depth += 1
                elif css[j] == ")":
                    depth -= 1
                j += 1
            out.append(css[i:j])
            i = j
            continue
        # whitespace runs
        if ch in " \t\r\n\f":
            j = i
            while j < n and css[j] in " \t\r\n\f":
                j += 1
            prev = out[-1][-1] if out and out[-1] else ""
            nxt = css[j] if j < n else ""
            if prev in trim_around or nxt in trim_around or prev == "" or nxt == "":
                pass  # drop whitespace
            else:
                out.append(" ")
            i = j
            continue
        out.append(ch)
        i += 1
    result = "".join(out)
    # drop a trailing semicolon before closing brace: ";}" -> "}"
    result = result.replace(";}", "}")
    return result.strip()


def minify_block(css: str) -> str:
    """Minify a declaration block (the content of a ``style`` attribute)."""
    minified = minify_css(css)
    if minified.endswith(";"):
        minified = minified[:-1]
    return minified


def _build_parents(node, parents, parent=None):
    parents[node] = parent
    if getattr(node, "type", None) in ("root", "element"):
        for child in node.children:
            _build_parents(child, parents, node)


def query_selector_all(node, selector, parents=None, strict=True):
    if parents is None:
        parents = {}
        _build_parents(node, parents)
    try:
        parsed = _cssselect_parse(selector)
    except SelectorSyntaxError:
        raise
    results = []

    def walk(n):
        for child in n.children:
            if child.type == "element":
                if any(_match(s.parsed_tree, child, parents, strict) for s in parsed):
                    results.append(child)
                walk(child)

    walk(node)
    return results


def query_selector(node, selector, parents=None, strict=True):
    results = query_selector_all(node, selector, parents, strict)
    return results[0] if results else None


def compare_specificity(a, b) -> int:
    for i in range(3):
        av = a[i] if i < len(a) else 0
        bv = b[i] if i < len(b) else 0
        if av < bv:
            return -1
        if av > bv:
            return 1
    return 0
