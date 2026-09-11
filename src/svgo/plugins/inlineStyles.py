import tinycss2
from cssselect import parse as _cssselect_parse
from cssselect.parser import (
    Attrib,
    Class,
    CombinedSelector,
    Element,
    Function,
    Hash,
    Pseudo,
    SelectorSyntaxError,
)

from .. import css
from ..collections import attrsGroups, pseudoClasses
from ..css import Declaration
from ..style import compare_specificity, includes_attr_selector
from ..visit import VISIT_SKIP
from ..xast import detach_node_from_parent

name = "inlineStyles"
description = "inline styles (additional options)"

_presentation = attrsGroups["presentation"]
_preserved_pseudos = set(pseudoClasses.get("functional", set())) | set(
    pseudoClasses.get("treeStructural", set())
)


import re as _re_mod


def _minify_selector(text):
    t = _re_mod.sub(r"\s+", " ", text.strip())
    t = _re_mod.sub(r"\s*([>+~])\s*", r"\1", t)
    return t


class _Selector:
    __slots__ = ("text", "canonical", "tree", "specificity", "rule", "matched")

    def __init__(self, text, tree, specificity, rule):
        self.text = text
        self.canonical = _minify_selector(text)
        self.tree = tree
        self.specificity = specificity
        self.rule = rule
        self.matched = None


class _Rule:
    __slots__ = ("selectors", "declarations", "style_node")

    def __init__(self, selectors, declarations, style_node):
        self.selectors = selectors  # list[_Selector]
        self.declarations = declarations  # list[Declaration]
        self.style_node = style_node


class _StyleEntry:
    __slots__ = ("node", "parent", "items")

    def __init__(self, node, parent, items):
        # items: ordered list of ("rule", _Rule) or ("raw", text)
        self.node = node
        self.parent = parent
        self.items = items


def _serialize_declarations(declarations):
    parts = []
    for d in declarations:
        imp = "!important" if d.important else ""
        parts.append(f"{d.name}:{d.value}{imp}")
    return ";".join(parts)


def _first_written_simple(tree):
    """Return the first *written* simple selector of the leftmost compound,
    mirroring csstree ``selector.children.first`` (ignoring the implicit
    universal ``*`` that cssselect inserts)."""
    node = tree
    # descend to leftmost compound
    while isinstance(node, CombinedSelector):
        node = node.selector
    # node is now the outermost wrapper of the leftmost compound; find the
    # innermost Element and the node that directly wraps it
    prev = None
    cur = node
    while cur is not None:
        if isinstance(cur, Element):
            # if explicit tag, the tag is the first written token; otherwise the
            # wrapper (prev) is
            if cur.element is not None and cur.element != "*":
                return cur
            return prev if prev is not None else cur
        prev = cur
        cur = getattr(cur, "selector", None)
    return node


def _selector_classes(tree):
    classes = []

    def walk(n):
        if isinstance(n, CombinedSelector):
            walk(n.selector)
            walk(n.subselector)
            return
        sub = getattr(n, "selector", None)
        if sub is not None:
            walk(sub)
        if isinstance(n, Class):
            classes.append(n.class_name)

    walk(tree)
    return classes


def fn(root, params, info):
    only_matched_once = params.get("onlyMatchedOnce", True)
    remove_matched_selectors = params.get("removeMatchedSelectors", True)
    use_mqs = params.get("useMqs", ["", "screen"])
    use_pseudos = params.get("usePseudos", [""])

    styles = []
    selectors = []

    def enter(node, parent_node):
        if node.name == "foreignObject":
            return VISIT_SKIP
        if node.name != "style" or len(node.children) == 0:
            return
        type_attr = node.attributes.get("type")
        if type_attr is not None and type_attr != "" and type_attr != "text/css":
            return

        css_text = "".join(
            child.value for child in node.children if child.type in ("text", "cdata")
        )

        try:
            nodes = tinycss2.parse_stylesheet(css_text, skip_comments=True, skip_whitespace=True)
        except Exception:
            return

        items = []
        for cnode in nodes:
            if cnode.type == "qualified-rule":
                prelude = tinycss2.serialize(cnode.prelude).strip()
                content = cnode.content if cnode.content is not None else []
                declarations = [
                    Declaration(css.decl_name(d), tinycss2.serialize(d.value).strip(), bool(d.important))
                    for d in tinycss2.parse_declaration_list(content, skip_comments=True, skip_whitespace=True)
                    if d.type == "declaration"
                ]
                rule = _Rule([], declarations, node)
                for sel_text in css._split_selector_list(prelude):
                    sel_text = sel_text.strip()
                    if not sel_text:
                        continue
                    processed = _process_pseudos(sel_text, use_pseudos)
                    if processed is None:
                        # selector kept with non-usable pseudos; still record for matching
                        processed = sel_text
                    try:
                        parsed = _cssselect_parse(processed)
                    except SelectorSyntaxError:
                        continue
                    for s in parsed:
                        entry = _Selector(processed, s.parsed_tree, s.specificity(), rule)
                        rule.selectors.append(entry)
                        selectors.append(entry)
                items.append(("rule", rule))
            elif cnode.type == "at-rule":
                items.append(("raw", tinycss2.serialize([cnode]).strip()))

        styles.append(_StyleEntry(node, parent_node, items))

    def root_exit(node, parent_node):
        if len(styles) == 0:
            return

        import functools

        sorted_selectors = sorted(
            selectors,
            key=functools.cmp_to_key(lambda a, b: compare_specificity(a.specificity, b.specificity)),
        )[::-1]

        parents = {}
        css._build_parents(root, parents)

        for selector in sorted_selectors:
            try:
                matched_elements = [
                    n for n in css.query_selector_all(root, selector.text, parents, strict=True)
                    if n.type == "element"
                ]
            except Exception:
                continue
            if len(matched_elements) == 0:
                continue
            if only_matched_once and len(matched_elements) > 1:
                continue

            for selected_el in matched_elements:
                _apply_rule_to_element(selected_el, selector.rule, selectors)

            if remove_matched_selectors and len(matched_elements) != 0:
                rule = selector.rule
                if selector in rule.selectors:
                    rule.selectors.remove(selector)
            selector.matched = matched_elements

        if not remove_matched_selectors:
            _regenerate(styles)
            return

        for selector in sorted_selectors:
            if selector.matched is None:
                continue
            if only_matched_once and len(selector.matched) > 1:
                continue
            for selected_el in selector.matched:
                class_list = []
                if selected_el.attributes.get("class") is not None:
                    class_list = selected_el.attributes["class"].split(" ")
                class_set = list(dict.fromkeys(class_list))

                for cname in _selector_classes(selector.tree):
                    if not any(
                        includes_attr_selector(s.text, "class", cname, True) for s in selectors
                    ):
                        if cname in class_set:
                            class_set.remove(cname)

                if len(class_set) == 0:
                    selected_el.attributes.pop("class", None)
                else:
                    selected_el.attributes["class"] = " ".join(class_set)

                leading = _first_written_simple(selector.tree)
                if (
                    isinstance(leading, Hash)
                    and selected_el.attributes.get("id") == leading.id
                    and not any(
                        includes_attr_selector(s.text, "id", leading.id, True) for s in selectors
                    )
                ):
                    selected_el.attributes.pop("id", None)

        _regenerate(styles)

    return {
        "element": {"enter": enter},
        "root": {"exit": root_exit},
    }


def _apply_rule_to_element(selected_el, rule, all_selectors):
    style_attr = selected_el.attributes.get("style") or ""
    decls = css.parse_style_declarations(style_attr)
    # first original declaration (new rule declarations are inserted before it,
    # mirroring csstree's insert-before-firstListItem)
    first_original = decls[0] if decls else None
    index_map = {}
    for i, d in enumerate(decls):
        index_map[d.name.lower()] = i

    for rule_decl in rule.declarations:
        prop = rule_decl.name
        if prop in _presentation and not any(
            includes_attr_selector(s.text, prop) for s in all_selectors
        ):
            selected_el.attributes.pop(prop, None)

        key = prop.lower()
        if key not in index_map:
            new_decl = Declaration(prop, rule_decl.value, rule_decl.important)
            if first_original is None:
                decls.append(new_decl)
            else:
                decls.insert(decls.index(first_original), new_decl)
            index_map = {d.name.lower(): i for i, d in enumerate(decls)}
        else:
            idx = index_map[key]
            if decls[idx].important is not True and rule_decl.important is True:
                decls[idx] = Declaration(prop, rule_decl.value, rule_decl.important)

    new_styles = _serialize_declarations(decls)
    if len(new_styles) != 0:
        selected_el.attributes["style"] = new_styles


def _process_pseudos(selector_text, use_pseudos):
    """Return the selector text with non-preserved pseudos removed when their
    combined text is listed in use_pseudos; otherwise return the original text.
    """
    try:
        parsed = _cssselect_parse(selector_text)
    except SelectorSyntaxError:
        return selector_text
    pseudos = _collect_non_preserved_pseudos(parsed[0].parsed_tree) if parsed else []
    combined = "".join(pseudos)
    if pseudos and combined in use_pseudos:
        return _strip_pseudos(selector_text, pseudos)
    return selector_text


def _collect_non_preserved_pseudos(tree):
    found = []

    def walk(n):
        sub = getattr(n, "selector", None)
        if sub is not None:
            walk(sub)
        if isinstance(n, CombinedSelector):
            walk(n.subselector)
        if isinstance(n, Pseudo):
            if n.ident not in _preserved_pseudos:
                found.append(":" + n.ident)
        if isinstance(n, Function):
            if n.name not in _preserved_pseudos:
                found.append(":" + n.name + "()")

    walk(tree)
    return found


def _strip_pseudos(selector_text, pseudos):
    # remove pseudo fragments from the raw selector text
    result = selector_text
    import re as _re

    result = _re.sub(r"::?[A-Za-z-]+(\([^)]*\))?", "", result)
    return result.strip()


def _regenerate(styles):
    for style in styles:
        rendered = []
        for kind, obj in style.items:
            if kind == "raw":
                rendered.append(obj)
            else:
                if len(obj.selectors) == 0:
                    continue
                prelude = ",".join(s.canonical for s in obj.selectors)
                block = _serialize_declarations(obj.declarations)
                rendered.append(prelude + "{" + block + "}")
        text = "".join(rendered)
        if text == "":
            detach_node_from_parent(style.node, style.parent)
        else:
            first_child = style.node.children[0]
            if first_child.type in ("text", "cdata"):
                first_child.value = text
