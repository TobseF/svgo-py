from ..pathutil import intersects, js2path, path2js
from ..style import collect_stylesheet, compute_style
from ..tools import includes_url_reference

name = "mergePaths"
description = "merges multiple paths in one if possible"


def _element_has_url(computed_style, att_name):
    style = computed_style.get(att_name)
    if style and style["type"] == "static":
        return includes_url_reference(style.get("value", ""))
    return False


def fn(root, params, info):
    force = params.get("force", False)
    float_precision = params.get("floatPrecision", 3)
    no_space_after_flags = params.get("noSpaceAfterFlags", False)
    stylesheet = collect_stylesheet(root)

    def enter(node):
        if len(node.children) <= 1:
            return

        elements_to_remove = set()
        prev_child = node.children[0]
        state = {"prev_path_data": None}

        def update_previous_path(child, path_data):
            js2path(child, path_data, {
                "floatPrecision": float_precision,
                "noSpaceAfterFlags": no_space_after_flags,
            })
            state["prev_path_data"] = None

        i = 1
        while i < len(node.children):
            child = node.children[i]

            if (
                prev_child.type != "element"
                or prev_child.name != "path"
                or len(prev_child.children) != 0
                or prev_child.attributes.get("d") is None
            ):
                if state["prev_path_data"] and prev_child.type == "element":
                    update_previous_path(prev_child, state["prev_path_data"])
                prev_child = child
                i += 1
                continue

            if (
                child.type != "element"
                or child.name != "path"
                or len(child.children) != 0
                or child.attributes.get("d") is None
            ):
                if state["prev_path_data"]:
                    update_previous_path(prev_child, state["prev_path_data"])
                prev_child = child
                i += 1
                continue

            computed = compute_style(stylesheet, child)
            if (
                computed.get("marker-start")
                or computed.get("marker-mid")
                or computed.get("marker-end")
                or computed.get("clip-path")
                or computed.get("mask")
                or computed.get("mask-image")
                or any(_element_has_url(computed, att) for att in ("fill", "filter", "stroke"))
            ):
                if state["prev_path_data"]:
                    update_previous_path(prev_child, state["prev_path_data"])
                prev_child = child
                i += 1
                continue

            child_attrs = list(child.attributes.keys())
            if len(child_attrs) != len(prev_child.attributes):
                if state["prev_path_data"]:
                    update_previous_path(prev_child, state["prev_path_data"])
                prev_child = child
                i += 1
                continue

            attrs_differ = any(
                attr != "d"
                and prev_child.type == "element"
                and prev_child.attributes.get(attr) != child.attributes.get(attr)
                for attr in child_attrs
            )
            if attrs_differ:
                if state["prev_path_data"]:
                    update_previous_path(prev_child, state["prev_path_data"])
                prev_child = child
                i += 1
                continue

            has_prev_path = state["prev_path_data"] is not None
            current_path_data = path2js(child)
            if state["prev_path_data"] is None:
                state["prev_path_data"] = path2js(prev_child)

            if force or not intersects(state["prev_path_data"], current_path_data):
                state["prev_path_data"].extend(current_path_data)
                elements_to_remove.add(child)
                i += 1
                continue

            if has_prev_path:
                update_previous_path(prev_child, state["prev_path_data"])

            prev_child = child
            state["prev_path_data"] = None
            i += 1

        if state["prev_path_data"] and prev_child.type == "element":
            update_previous_path(prev_child, state["prev_path_data"])

        node.children = [c for c in node.children if c not in elements_to_remove]

    return {"element": {"enter": lambda node, parent_node: enter(node)}}
