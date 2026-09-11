from ..collections import elems
from ..xast import Element, Text

name = "removeXlink"
description = (
    "remove xlink namespace and replaces attributes with the SVG 2 equivalent where applicable"
)

_XLINK_NS = "http://www.w3.org/1999/xlink"
_SHOW_TO_TARGET = {"new": "_blank", "replace": "_self"}
_LEGACY_ELEMENTS = {"cursor", "filter", "font-face-uri", "glyphRef", "tref"}


def _find_prefixed_attrs(node, prefixes, attr):
    return [f"{prefix}:{attr}" for prefix in prefixes if node.attributes.get(f"{prefix}:{attr}") is not None]


def fn(root, params, info):
    include_legacy = params.get("includeLegacy")
    xlink_prefixes = []
    overridden_prefixes = []
    used_in_legacy = []

    def enter(node):
        for key, value in list(node.attributes.items()):
            if key.startswith("xmlns:"):
                prefix = key.split(":")[1]
                if value == _XLINK_NS:
                    xlink_prefixes.append(prefix)
                    continue
                if prefix in xlink_prefixes:
                    overridden_prefixes.append(prefix)

        if any(prefix in xlink_prefixes for prefix in overridden_prefixes):
            return

        show_attrs = _find_prefixed_attrs(node, xlink_prefixes, "show")
        show_handled = node.attributes.get("target") is not None
        for i in range(len(show_attrs) - 1, -1, -1):
            attr = show_attrs[i]
            value = node.attributes[attr]
            mapping = _SHOW_TO_TARGET.get(value)
            if show_handled or mapping is None:
                del node.attributes[attr]
                continue
            default_target = (elems.get(node.name) or {}).get("defaults", {}).get("target")
            if mapping != default_target:
                node.attributes["target"] = mapping
            del node.attributes[attr]
            show_handled = True

        title_attrs = _find_prefixed_attrs(node, xlink_prefixes, "title")
        for i in range(len(title_attrs) - 1, -1, -1):
            attr = title_attrs[i]
            value = node.attributes[attr]
            has_title = [c for c in node.children if c.type == "element" and c.name == "title"]
            if len(has_title) > 0:
                del node.attributes[attr]
                continue
            title_tag = Element("title", {}, [Text(value)])
            node.children.insert(0, title_tag)
            del node.attributes[attr]

        href_attrs = _find_prefixed_attrs(node, xlink_prefixes, "href")
        if len(href_attrs) > 0 and node.name in _LEGACY_ELEMENTS and not include_legacy:
            for attr in href_attrs:
                used_in_legacy.append(attr.split(":", 1)[0])
            return

        for i in range(len(href_attrs) - 1, -1, -1):
            attr = href_attrs[i]
            value = node.attributes[attr]
            if node.attributes.get("href") is not None:
                del node.attributes[attr]
                continue
            node.attributes["href"] = value
            del node.attributes[attr]

    def exit(node):
        for key, value in list(node.attributes.items()):
            parts = key.split(":")
            prefix = parts[0]
            attr = parts[1] if len(parts) > 1 else None

            if (
                prefix in xlink_prefixes
                and prefix not in overridden_prefixes
                and prefix not in used_in_legacy
                and not include_legacy
            ):
                del node.attributes[key]
                continue

            if key.startswith("xmlns:") and attr not in used_in_legacy:
                if value == _XLINK_NS:
                    if attr in xlink_prefixes:
                        xlink_prefixes.remove(attr)
                    node.attributes.pop(key, None)
                    continue
                if prefix in overridden_prefixes:
                    if attr in overridden_prefixes:
                        overridden_prefixes.remove(attr)

    return {
        "element": {
            "enter": lambda node, parent_node: enter(node),
            "exit": lambda node, parent_node: exit(node),
        }
    }
