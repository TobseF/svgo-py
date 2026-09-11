import urllib.parse

from ..tools import find_references, has_scripts
from ..visit import VISIT_SKIP

name = "cleanupIds"
description = "removes unused IDs and minifies used"

_GEN_CHARS = [chr(c) for c in range(ord("a"), ord("z") + 1)] + [
    chr(c) for c in range(ord("A"), ord("Z") + 1)
]
_MAX_ID_INDEX = len(_GEN_CHARS) - 1


def _encode_uri(s):
    # mirror JavaScript encodeURI (keeps a broad set of characters unescaped)
    return urllib.parse.quote(s, safe="A-Za-z0-9-_.!~*'();/?:@&=+$,#")


def _has_string_prefix(string, prefixes):
    return any(string.startswith(p) for p in prefixes)


def _generate_id(current_id):
    if current_id is None:
        return [0]
    current_id[-1] += 1
    for i in range(len(current_id) - 1, 0, -1):
        if current_id[i] > _MAX_ID_INDEX:
            current_id[i] = 0
            if i - 1 >= 0:
                current_id[i - 1] += 1
    if current_id[0] > _MAX_ID_INDEX:
        current_id[0] = 0
        current_id.insert(0, 0)
    return current_id


def _get_id_string(arr):
    return "".join(_GEN_CHARS[i] for i in arr)


def fn(root, params, info):
    remove = params.get("remove", True)
    minify = params.get("minify", True)
    preserve = params.get("preserve", [])
    preserve_prefixes = params.get("preservePrefixes", [])
    force = params.get("force", False)

    if isinstance(preserve, str):
        preserve = [preserve]
    preserve_ids = set(preserve or [])
    if isinstance(preserve_prefixes, str):
        preserve_prefixes = [preserve_prefixes]
    preserve_id_prefixes = list(preserve_prefixes or [])

    node_by_id = {}
    references_by_id = {}  # preserves insertion order
    state = {"deoptimized": False}

    def enter(node):
        if not force:
            if (node.name == "style" and len(node.children) != 0) or has_scripts(node):
                state["deoptimized"] = True
                return
            if node.name == "svg":
                has_defs_only = True
                for child in node.children:
                    if child.type != "element" or child.name != "defs":
                        has_defs_only = False
                        break
                if has_defs_only:
                    return VISIT_SKIP

        for attr_name, value in list(node.attributes.items()):
            if attr_name == "id":
                id_ = value
                if id_ in node_by_id:
                    del node.attributes["id"]
                else:
                    node_by_id[id_] = node
            else:
                ids = find_references(attr_name, value)
                for id_ in ids:
                    references_by_id.setdefault(id_, []).append(
                        {"element": node, "name": attr_name}
                    )

    def is_id_preserved(id_):
        return id_ in preserve_ids or _has_string_prefix(id_, preserve_id_prefixes)

    def root_exit(node, parent_node):
        if state["deoptimized"]:
            return
        current_id = [None]  # use list cell to mimic mutable ?number[]
        current_id[0] = None
        cid = None
        for id_, refs in list(references_by_id.items()):
            target = node_by_id.get(id_)
            if target is not None:
                if minify and is_id_preserved(id_) is False:
                    while True:
                        cid = _generate_id(cid)
                        current_id_string = _get_id_string(cid)
                        if not (
                            is_id_preserved(current_id_string)
                            or (current_id_string in references_by_id and node_by_id.get(current_id_string) is None)
                        ):
                            break
                    target.attributes["id"] = current_id_string
                    for ref in refs:
                        element = ref["element"]
                        nm = ref["name"]
                        value = element.attributes[nm]
                        if "#" in value:
                            value = value.replace(f"#{_encode_uri(id_)}", f"#{current_id_string}")
                            value = value.replace(f"#{id_}", f"#{current_id_string}")
                            element.attributes[nm] = value
                        else:
                            element.attributes[nm] = value.replace(
                                f"{id_}.", f"{current_id_string}."
                            )
                del node_by_id[id_]
        if remove:
            for id_, target in list(node_by_id.items()):
                if is_id_preserved(id_) is False:
                    target.attributes.pop("id", None)

    return {
        "element": {"enter": lambda node, parent_node: enter(node)},
        "root": {"exit": root_exit},
    }
