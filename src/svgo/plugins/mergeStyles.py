from ..visit import VISIT_SKIP
from ..xast import Cdata, Text, detach_node_from_parent

name = "mergeStyles"
description = "merge multiple style elements into one"


def fn(root, params, info):
    state = {"first": None, "collected": "", "content_type": "text"}

    def enter(node, parent_node):
        if node.name == "foreignObject":
            return VISIT_SKIP
        if node.name != "style":
            return None

        type_attr = node.attributes.get("type")
        if type_attr is not None and type_attr != "" and type_attr != "text/css":
            return None

        css = ""
        for child in node.children:
            if child.type == "text":
                css += child.value
            if child.type == "cdata":
                state["content_type"] = "cdata"
                css += child.value

        if len(css.strip()) == 0:
            detach_node_from_parent(node, parent_node)
            return None

        media = node.attributes.get("media")
        if media is None:
            state["collected"] += css
        else:
            state["collected"] += f"@media {media}{{{css}}}"
            del node.attributes["media"]

        if state["first"] is None:
            state["first"] = node
        else:
            detach_node_from_parent(node, parent_node)
            if state["content_type"] == "cdata":
                child = Cdata(state["collected"])
            else:
                child = Text(state["collected"])
            state["first"].children = [child]
        return None

    return {"element": {"enter": enter}}
