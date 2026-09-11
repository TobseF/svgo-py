from .. import css
from ..tools import has_scripts
from ..xast import Cdata, Text, detach_node_from_parent

name = "minifyStyles"
description = "minifies styles and removes unused styles"

# NOTE: SVGO uses the JS `csso` library, which performs structural CSS
# optimizations (shorthand merging, rule restructuring, usage-based dead-code
# elimination). This port provides whitespace/comment-level minification only
# -- there is no pure-Python equivalent of csso. Output therefore matches csso
# for simple stylesheets but not where csso applies semantic optimizations.


def fn(root, params, info):
    style_elements = []  # (node, parent)
    elements_with_style_attr = []
    deoptimized = [False]

    def enter(node, parent_node):
        if has_scripts(node):
            deoptimized[0] = True
        if node.name == "style" and len(node.children) != 0:
            style_elements.append((node, parent_node))
        elif node.attributes.get("style") is not None:
            elements_with_style_attr.append(node)

    def root_exit(node, parent_node):
        for style_node, style_parent in style_elements:
            first = style_node.children[0]
            if first.type in ("text", "cdata"):
                css_text = first.value
                minified = css.minify_css(css_text)
                if len(minified) == 0:
                    detach_node_from_parent(style_node, style_parent)
                    continue
                # preserve cdata if the content contains markup characters
                if ">" in css_text or "<" in css_text:
                    style_node.children[0] = Cdata(minified)
                else:
                    style_node.children[0] = Text(minified)

        for node in elements_with_style_attr:
            elem_style = node.attributes["style"]
            node.attributes["style"] = css.minify_block(elem_style)

    return {
        "element": {"enter": enter},
        "root": {"exit": root_exit},
    }
