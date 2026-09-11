import re

from ..xast import detach_node_from_parent

name = "removeComments"
description = "removes comments"

DEFAULT_PRESERVE_PATTERNS = [r"^!"]


def fn(root, params, info):
    preserve_patterns = params.get("preservePatterns", DEFAULT_PRESERVE_PATTERNS)

    def enter(node, parent_node):
        if preserve_patterns:
            if not isinstance(preserve_patterns, (list, tuple)):
                raise ValueError(
                    "Expected array in removeComments preservePatterns parameter "
                    f"but received {preserve_patterns}"
                )
            matches = any(re.search(pattern, node.value) for pattern in preserve_patterns)
            if matches:
                return
        detach_node_from_parent(node, parent_node)

    return {"comment": {"enter": enter}}
