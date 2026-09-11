import sys

name = "addClassesToSVGElement"
description = "adds classnames to an outer <svg> element"


def fn(root, params, info):
    class_names = params.get("classNames")
    if not (isinstance(class_names, list) and len(class_names) != 0) and not params.get("className"):
        print('Error in plugin "addClassesToSVGElement": absent parameters.', file=sys.stderr)
        return None
    names = class_names if class_names is not None else [params.get("className")]

    def enter(node, parent_node):
        if node.name == "svg" and parent_node.type == "root":
            cls = node.attributes.get("class")
            class_list = list(dict.fromkeys(cls.split(" "))) if cls is not None else []
            for class_name in names:
                if class_name is not None:
                    to_add = class_name if isinstance(class_name, str) else class_name(node, info)
                    if to_add not in class_list:
                        class_list.append(to_add)
            node.attributes["class"] = " ".join(class_list)

    return {"element": {"enter": enter}}
