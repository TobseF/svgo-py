from ..collections import attrsGroups
from ..tools import is_executable_url
from ..xast import detach_node_from_parent

name = "removeScripts"
description = "removes scripts"

_event_attrs = (
    list(attrsGroups.get("animationEvent", set()))
    + list(attrsGroups.get("documentEvent", set()))
    + list(attrsGroups.get("documentElementEvent", set()))
    + list(attrsGroups.get("globalEvent", set()))
    + list(attrsGroups.get("graphicalEvent", set()))
)

_SVG_NS = "http://www.w3.org/2000/svg"
_FOREIGN_OBJECT_NS = [_SVG_NS]
_ANCHOR_NS = [_SVG_NS]
_SCRIPT_NS = [_SVG_NS, "http://www.w3.org/1999/xhtml"]
_HTML_URL_ATTRS = {"action", "data", "formaction", "href", "src"}


def _is_namespace_aware_elem(elem, target_elem, prefixes, target_namespaces):
    if elem == target_elem:
        return True
    if ":" in elem:
        prefix, effective_tag = elem.split(":", 1)
        if target_elem == effective_tag:
            namespaces = prefixes.get(prefix)
            if not namespaces:
                return False
            namespace = namespaces[-1]
            return namespace in target_namespaces
    return False


def fn(root, params, info):
    prefixes = {}
    state = {"foreign_depth": 0}

    def enter(node, parent_node):
        for k, v in node.attributes.items():
            if not k.startswith("xmlns:"):
                continue
            prefix = k[6:]
            prefixes.setdefault(prefix, []).append(v)

        if _is_namespace_aware_elem(node.name, "foreignObject", prefixes, _FOREIGN_OBJECT_NS):
            state["foreign_depth"] += 1

        if _is_namespace_aware_elem(node.name, "script", prefixes, _SCRIPT_NS):
            detach_node_from_parent(node, parent_node)
            return

        for attr, value in list(node.attributes.items()):
            local_attr = attr[attr.rfind(":") + 1:].lower()
            is_event_attr = attr in _event_attrs or (
                state["foreign_depth"] > 0 and local_attr.startswith("on")
            )
            is_embedded_doc_attr = state["foreign_depth"] > 0 and local_attr == "srcdoc"
            is_executable_html_url = (
                state["foreign_depth"] > 0
                and local_attr in _HTML_URL_ATTRS
                and value is not None
                and is_executable_url(value)
            )
            if is_event_attr or is_embedded_doc_attr or is_executable_html_url:
                del node.attributes[attr]

    def exit(node, parent_node):
        is_foreign_object = _is_namespace_aware_elem(node.name, "foreignObject", prefixes, _FOREIGN_OBJECT_NS)
        is_anchor = _is_namespace_aware_elem(node.name, "a", prefixes, _ANCHOR_NS)

        for k in list(node.attributes.keys()):
            if not k.startswith("xmlns:"):
                continue
            prefix = k[6:]
            if prefixes.get(prefix):
                prefixes[prefix].pop()

        if is_anchor:
            for attr in list(node.attributes.keys()):
                if attr == "href" or attr.endswith(":href"):
                    value = node.attributes.get(attr)
                    if value is None or not is_executable_url(value):
                        continue
                    index = next((i for i, c in enumerate(parent_node.children) if c is node), None)
                    if index is None:
                        continue
                    useful_children = [c for c in node.children if c.type != "text"]
                    parent_node.children[index:index + 1] = useful_children

        if is_foreign_object:
            state["foreign_depth"] -= 1

    return {"element": {"enter": enter, "exit": exit}}
