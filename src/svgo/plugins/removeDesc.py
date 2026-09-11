import re

from ..xast import detach_node_from_parent

name = "removeDesc"
description = "removes <desc>"

_standard_descs = re.compile(r"^(Created with|Created using)")


def fn(root, params, info):
    remove_any = params.get("removeAny", False)

    def enter(node, parent_node):
        if node.name == "desc":
            if (
                remove_any
                or len(node.children) == 0
                or (
                    node.children[0].type == "text"
                    and _standard_descs.search(node.children[0].value)
                )
            ):
                detach_node_from_parent(node, parent_node)

    return {"element": {"enter": enter}}
