from ..style import collect_stylesheet
from ..xast import Element, detach_node_from_parent

name = "reusePaths"
description = (
    "Finds <path> elements with the same d, fill, and stroke, and converts them "
    "to <use> elements referencing a single <path> def."
)


def fn(root, params, info):
    stylesheet = collect_stylesheet(root)
    paths = {}  # key -> list of nodes (insertion-ordered)
    state = {"svg_defs": None}
    hrefs = set()

    def enter(node, parent_node):
        if node.name == "path" and node.attributes.get("d") is not None:
            d = node.attributes["d"]
            fill = node.attributes.get("fill") or ""
            stroke = node.attributes.get("stroke") or ""
            key = d + ";s:" + stroke + ";f:" + fill
            paths.setdefault(key, []).append(node)

        if (
            state["svg_defs"] is None
            and node.name == "defs"
            and parent_node.type == "element"
            and parent_node.name == "svg"
        ):
            state["svg_defs"] = node

        if node.name == "use":
            for nm in ("href", "xlink:href"):
                href = node.attributes.get(nm)
                if href is not None and href.startswith("#") and len(href) > 1:
                    hrefs.add(href[1:])

    def exit(node, parent_node):
        if node.name != "svg" or parent_node.type != "root":
            return
        defs_tag = state["svg_defs"]
        if defs_tag is None:
            defs_tag = Element("defs", {}, [])

        index = [0]
        for list_ in paths.values():
            if len(list_) <= 1:
                continue
            reusable = Element("path", {}, [])
            for attr in ("fill", "stroke", "d"):
                if list_[0].attributes.get(attr) is not None:
                    reusable.attributes[attr] = list_[0].attributes[attr]

            original_id = list_[0].attributes.get("id")
            if (
                original_id is None
                or original_id in hrefs
                or any(rule.selector == f"#{original_id}" for rule in stylesheet.rules)
            ):
                reusable.attributes["id"] = "reuse-" + str(index[0])
                index[0] += 1
            else:
                reusable.attributes["id"] = original_id
                del list_[0].attributes["id"]
            defs_tag.children.append(reusable)

            for path_node in list_:
                path_node.attributes.pop("d", None)
                path_node.attributes.pop("stroke", None)
                path_node.attributes.pop("fill", None)

                if any(c is path_node for c in defs_tag.children) and len(path_node.children) == 0:
                    if len(path_node.attributes) == 0:
                        detach_node_from_parent(path_node, defs_tag)
                        continue
                    if len(path_node.attributes) == 1 and path_node.attributes.get("id") is not None:
                        detach_node_from_parent(path_node, defs_tag)
                        pid = path_node.attributes["id"]
                        for child in _find_href_refs(node, pid):
                            for nm in ("href", "xlink:href"):
                                if child.attributes.get(nm) is not None:
                                    child.attributes[nm] = "#" + reusable.attributes["id"]
                        continue

                path_node.name = "use"
                path_node.attributes["xlink:href"] = "#" + reusable.attributes["id"]

        if len(defs_tag.children) != 0:
            if node.attributes.get("xmlns:xlink") is None:
                node.attributes["xmlns:xlink"] = "http://www.w3.org/1999/xlink"
            if state["svg_defs"] is None:
                node.children.insert(0, defs_tag)

    return {"element": {"enter": enter, "exit": exit}}


def _find_href_refs(root, target_id):
    """Equivalent of querySelectorAll for `[href=#id], [xlink:href=#id]`."""
    ref = "#" + target_id
    results = []

    def walk(n):
        for child in n.children:
            if child.type == "element":
                if child.attributes.get("href") == ref or child.attributes.get("xlink:href") == ref:
                    results.append(child)
                walk(child)

    walk(root)
    return results
