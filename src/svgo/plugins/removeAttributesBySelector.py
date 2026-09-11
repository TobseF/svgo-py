import sys

from ..css import query_selector_all

name = "removeAttributesBySelector"
description = "removes attributes of elements that match a css selector"


def fn(root, params, info):
    if not isinstance(params.get("selectors"), list) and (
        not params.get("selector") or not params.get("attributes")
    ):
        print('Warning: The plugin "removeAttributesBySelector" is missing parameters.', file=sys.stderr)
        return None

    selectors = params["selectors"] if isinstance(params.get("selectors"), list) else [params]
    for spec in selectors:
        selector = spec["selector"]
        attributes = spec["attributes"]
        try:
            nodes = query_selector_all(root, selector, strict=True)
        except Exception:
            nodes = []
        for node in nodes:
            if node.type == "element":
                if isinstance(attributes, (list, tuple)):
                    for attr_name in attributes:
                        node.attributes.pop(attr_name, None)
                else:
                    node.attributes.pop(attributes, None)
    return {}
