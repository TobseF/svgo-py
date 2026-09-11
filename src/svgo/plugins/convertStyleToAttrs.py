import re

from ..collections import attrsGroups

name = "convertStyleToAttrs"
description = "converts style to attributes"

_styling_props = attrsGroups["presentation"]


def _g(*args):
    return "(?:" + "|".join(args) + ")"


_rEscape = r"\\(?:[0-9a-f]{1,6}\s?|\r\n|.)"
_rAttr = r"\s*(" + _g(r"[^:;\\]", _rEscape) + r"*?)\s*"
_rSingleQuotes = r"'(?:[^'\n\r\\]|" + _rEscape + r")*?(?:'|$)"
_rQuotes = r'"(?:[^"\n\r\\]|' + _rEscape + r')*?(?:"|$)'
_rQuotedString = re.compile("^" + _g(_rSingleQuotes, _rQuotes) + "$")
_rParenthesis = r"\(" + _g(r"[^'\"()\\]+", _rEscape, _rSingleQuotes, _rQuotes) + r"*?" + r"\)"
_rValue = r"\s*(" + _g(r"[^!'\"();\\]+?", _rEscape, _rSingleQuotes, _rQuotes, _rParenthesis, r"[^;]*?") + r"*?" + r")"
_rDeclEnd = r"\s*(?:;\s*|$)"
_rImportant = r"(\s*!important(?![-(\w]))?"
_reg_declaration_block = re.compile(_rAttr + ":" + _rValue + _rImportant + _rDeclEnd, re.I)
_reg_strip_comments = re.compile(_g(_rEscape, _rSingleQuotes, _rQuotes, r"/\*[\s\S]*?\*/"), re.I)
_reg_gz = re.compile(r"[-g-z]", re.I)


def _strip_comment(m):
    match = m.group(0)
    if match[0] == "/":
        return ""
    if match[0] == "\\" and len(match) > 1 and _reg_gz.match(match[1]):
        return match[1]
    return match


def fn(root, params, info):
    keep_important = params.get("keepImportant", False)

    def enter(node):
        style = node.attributes.get("style")
        if style is None:
            return
        styles = []
        new_attributes = {}

        style_value = _reg_strip_comments.sub(_strip_comment, style)

        for m in _reg_declaration_block.finditer(style_value):
            important = m.group(3)
            if not keep_important or not important:
                styles.append([m.group(1), m.group(2) or ""])

        if styles:
            kept = []
            for style_pair in styles:
                keep = True
                if style_pair[0]:
                    prop = style_pair[0].lower()
                    val = style_pair[1]
                    if _rQuotedString.match(val):
                        val = val[1:-1]
                    if prop in _styling_props:
                        new_attributes[prop] = val
                        keep = False
                if keep:
                    kept.append(style_pair)
            styles = kept

            for k, v in new_attributes.items():
                node.attributes[k] = v

            if styles:
                node.attributes["style"] = ";".join(":".join(s) for s in styles)
            else:
                node.attributes.pop("style", None)

    return {"element": {"enter": lambda node, parent_node: enter(node)}}
