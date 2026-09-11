import re

import tinycss2

from ..collections import referencesProps

name = "prefixIds"
description = "prefix IDs"

_reg_basename = re.compile(r"[/\\]?([^/\\]+)$")
_reg_escape = re.compile(r"[. ]")
_reg_split_ws = re.compile(r"\s+")
_reg_split_begin = re.compile(r"\s*;\s+")
# JS: /\burl\((["'])?(#.+?)\1\)/gi
_reg_url = re.compile(r"\burl\((?:\"(#.+?)\"|'(#.+?)'|(#.+?))\)", re.I)


def _get_basename(path):
    m = _reg_basename.search(path)
    return m.group(1) if m else ""


def _escape_identifier(s):
    return _reg_escape.sub("_", s)


def _unquote(s):
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s


def _prefix_id(gen, body):
    prefix = gen(body)
    if body.startswith(prefix):
        return body
    return prefix + body


def _prefix_reference(gen, reference):
    if reference.startswith("#"):
        return "#" + _prefix_id(gen, reference[1:])
    return None


def _generate_prefix(body, node, info, prefix_gen, delim, history):
    if callable(prefix_gen):
        prefix = history.get(body)
        if prefix is not None:
            return prefix
        prefix = prefix_gen(node, info) + delim
        history[body] = prefix
        return prefix
    if isinstance(prefix_gen, str):
        return prefix_gen + delim
    if prefix_gen is False:
        return ""
    path = info.get("path")
    if path is not None and len(path) > 0:
        return _escape_identifier(_get_basename(path)) + delim
    return "prefix" + delim


def fn(root, params, info):
    delim = params.get("delim", "__")
    prefix = params.get("prefix")
    prefix_ids = params.get("prefixIds", True)
    prefix_class_names = params.get("prefixClassNames", True)
    prefix_map = {}

    def enter(node):
        def gen(id_):
            return _generate_prefix(id_, node, info, prefix, delim, prefix_map)

        if node.name == "style":
            if len(node.children) == 0:
                return
            for child in node.children:
                if child.type not in ("text", "cdata"):
                    continue
                try:
                    child.value = _prefix_css(child.value, gen, prefix_ids, prefix_class_names)
                except Exception:
                    return

        if prefix_ids and node.attributes.get("id") is not None and len(node.attributes["id"]) != 0:
            node.attributes["id"] = _prefix_id(gen, node.attributes["id"])

        if prefix_class_names and node.attributes.get("class") is not None and len(node.attributes["class"]) != 0:
            node.attributes["class"] = " ".join(
                _prefix_id(gen, nm) for nm in _reg_split_ws.split(node.attributes["class"])
            )

        for attr in ("href", "xlink:href"):
            val = node.attributes.get(attr)
            if val is not None and len(val) != 0:
                prefixed = _prefix_reference(gen, val)
                if prefixed is not None:
                    node.attributes[attr] = prefixed

        for attr in referencesProps:
            val = node.attributes.get(attr)
            if val is not None and len(val) != 0:
                def repl(m):
                    url = m.group(1) or m.group(2) or m.group(3)
                    prefixed = _prefix_reference(gen, url)
                    return m.group(0) if prefixed is None else f"url({prefixed})"

                node.attributes[attr] = _reg_url.sub(repl, val)

        for attr in ("begin", "end"):
            val = node.attributes.get(attr)
            if val is not None and len(val) != 0:
                parts = []
                for piece in _reg_split_begin.split(val):
                    if piece.endswith(".end") or piece.endswith(".start"):
                        seg = piece.split(".")
                        parts.append(f"{_prefix_id(gen, seg[0])}.{seg[1]}")
                    else:
                        parts.append(piece)
                node.attributes[attr] = "; ".join(parts)

    return {"element": {"enter": lambda node, parent_node: enter(node)}}


# ---------------------------------------------------------------------------
# <style> CSS prefixing (token-based, minified output ~ csstree.generate)
# ---------------------------------------------------------------------------

def _prefix_css(css_text, gen, prefix_ids, prefix_class_names):
    nodes = tinycss2.parse_stylesheet(css_text, skip_comments=True, skip_whitespace=True)
    return "".join(_render_node(n, gen, prefix_ids, prefix_class_names) for n in nodes)


def _render_node(node, gen, prefix_ids, prefix_class_names):
    if node.type == "qualified-rule":
        prelude = _prefix_selector_tokens(node.prelude, gen, prefix_ids, prefix_class_names)
        content = _prefix_block(node.content or [], gen, prefix_ids, prefix_class_names)
        return prelude + "{" + content + "}"
    if node.type == "at-rule":
        header = "@" + node.at_keyword + _minify_ws(tinycss2.serialize(node.prelude))
        header = header.rstrip()
        if node.content is None:
            return header + ";"
        inner = tinycss2.parse_stylesheet(
            tinycss2.serialize(node.content), skip_comments=True, skip_whitespace=True
        )
        # keyframe/media blocks: recurse; declaration-only at-rules (@font-face)
        if any(n.type in ("qualified-rule", "at-rule") for n in inner):
            body = "".join(_render_node(n, gen, prefix_ids, prefix_class_names) for n in inner)
        else:
            body = _prefix_block(node.content, gen, prefix_ids, prefix_class_names)
        return header + "{" + body + "}"
    return tinycss2.serialize([node])


def _prefix_selector_tokens(tokens, gen, prefix_ids, prefix_class_names):
    out = []
    i = 0
    n = len(tokens)
    while i < n:
        t = tokens[i]
        tt = t.type
        if tt == "hash" and prefix_ids:
            out.append("#" + _prefix_id(gen, t.value))
        elif tt == "literal" and t.value == "." and prefix_class_names and i + 1 < n and tokens[i + 1].type == "ident":
            out.append("." + _prefix_id(gen, tokens[i + 1].value))
            i += 2
            continue
        elif tt == "url":
            prefixed = _prefix_reference(gen, t.value)
            out.append("url(" + (t.value if prefixed is None else prefixed) + ")")
        else:
            out.append(tinycss2.serialize([t]))
        i += 1
    return _minify_selector("".join(out))


def _prefix_block(content_tokens, gen, prefix_ids, prefix_class_names):
    decls = tinycss2.parse_declaration_list(content_tokens, skip_comments=True, skip_whitespace=True)
    parts = []
    for d in decls:
        if d.type != "declaration":
            continue
        value = _prefix_value_tokens(d.value, gen)
        important = "!important" if d.important else ""
        prop = d.name if d.name.startswith("--") else d.lower_name
        parts.append(f"{prop}:{value}{important}")
    return ";".join(parts)


def _prefix_value_tokens(tokens, gen):
    out = []
    for t in tokens:
        if t.type == "url":
            prefixed = _prefix_reference(gen, t.value)
            out.append("url(" + (t.value if prefixed is None else prefixed) + ")")
        elif t.type == "function" and t.lower_name == "url":
            inner = tinycss2.serialize(t.arguments).strip()
            unq = _unquote(inner)
            prefixed = _prefix_reference(gen, unq)
            if prefixed is not None:
                out.append(f"url({prefixed})")
            else:
                out.append(tinycss2.serialize([t]))
        else:
            out.append(tinycss2.serialize([t]))
    return _minify_ws("".join(out)).strip()


def _minify_selector(text):
    t = re.sub(r"\s+", " ", text.strip())
    t = re.sub(r"\s*([>+~])\s*", r"\1", t)
    return t


def _minify_ws(text):
    return re.sub(r"\s+", " ", text)
