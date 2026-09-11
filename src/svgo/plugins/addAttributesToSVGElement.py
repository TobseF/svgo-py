import sys

name = "addAttributesToSVGElement"
description = "adds attributes to an outer <svg> element"


def fn(root, params, info):
    if not isinstance(params.get("attributes"), list) and not params.get("attribute"):
        print('Error in plugin "addAttributesToSVGElement": absent parameters.', file=sys.stderr)
        return None
    attrs = params["attributes"] if params.get("attributes") is not None else [params.get("attribute")]

    def enter(node, parent_node):
        if node.name == "svg" and parent_node.type == "root":
            for attribute in attrs:
                if isinstance(attribute, str):
                    if node.attributes.get(attribute) is None:
                        node.attributes[attribute] = None
                elif isinstance(attribute, dict):
                    for key in attribute.keys():
                        if node.attributes.get(key) is None:
                            node.attributes[key] = attribute[key]

    return {"element": {"enter": enter}}
