from ..collections import elemsGroups
from ..css import query_selector
from ..path import parse_path_data
from ..style import collect_stylesheet, compute_style
from ..tools import find_references, has_scripts
from ..visit import VISIT_SKIP, visit
from ..xast import detach_node_from_parent

name = "removeHiddenElems"
description = "removes hidden elements (zero sized, with absent attributes)"

_non_rendering = elemsGroups["nonRendering"]


def fn(root, params, info):
    p = params
    isHidden = p.get("isHidden", True)
    displayNone = p.get("displayNone", True)
    opacity0 = p.get("opacity0", True)
    circleR0 = p.get("circleR0", True)
    ellipseRX0 = p.get("ellipseRX0", True)
    ellipseRY0 = p.get("ellipseRY0", True)
    rectWidth0 = p.get("rectWidth0", True)
    rectHeight0 = p.get("rectHeight0", True)
    patternWidth0 = p.get("patternWidth0", True)
    patternHeight0 = p.get("patternHeight0", True)
    imageWidth0 = p.get("imageWidth0", True)
    imageHeight0 = p.get("imageHeight0", True)
    pathEmptyD = p.get("pathEmptyD", True)
    polylineEmptyPoints = p.get("polylineEmptyPoints", True)
    polygonEmptyPoints = p.get("polygonEmptyPoints", True)

    stylesheet = collect_stylesheet(root)

    non_rendered_nodes = {}  # node -> parent (insertion ordered)
    removed_def_ids = set()
    all_defs = {}
    all_references = set()
    references_by_id = {}
    state = {"deoptimized": False}

    def can_remove_non_rendering_node(node):
        if node.attributes.get("id") in all_references:
            return False
        for child in node.children:
            if child.type == "element" and not can_remove_non_rendering_node(child):
                return False
        return True

    def remove_element(node, parent_node):
        if (
            node.type == "element"
            and node.attributes.get("id") is not None
            and parent_node.type == "element"
            and parent_node.name == "defs"
        ):
            removed_def_ids.add(node.attributes["id"])
        detach_node_from_parent(node, parent_node)

    # pre-pass: opacity 0
    def pre_enter(node, parent_node):
        if node.name in _non_rendering:
            non_rendered_nodes[node] = parent_node
            return VISIT_SKIP
        computed = compute_style(stylesheet, node)
        op = computed.get("opacity")
        if opacity0 and op and op["type"] == "static" and op.get("value") == "0":
            if node.name == "path":
                non_rendered_nodes[node] = parent_node
                return VISIT_SKIP
            remove_element(node, parent_node)

    visit(root, {"element": {"enter": pre_enter}})

    def enter(node, parent_node):
        if (node.name == "style" and len(node.children) != 0) or has_scripts(node):
            state["deoptimized"] = True
            return

        if node.name == "defs":
            all_defs[node] = parent_node

        if node.name == "use":
            for attr in node.attributes.keys():
                if attr != "href" and not attr.endswith(":href"):
                    continue
                value = node.attributes[attr]
                id_ = value[1:]
                references_by_id.setdefault(id_, []).append((node, parent_node))

        attrs = node.attributes

        if circleR0 and node.name == "circle" and len(node.children) == 0 and attrs.get("r") == "0":
            remove_element(node, parent_node); return
        if ellipseRX0 and node.name == "ellipse" and len(node.children) == 0 and attrs.get("rx") == "0":
            remove_element(node, parent_node); return
        if ellipseRY0 and node.name == "ellipse" and len(node.children) == 0 and attrs.get("ry") == "0":
            remove_element(node, parent_node); return
        if rectWidth0 and node.name == "rect" and len(node.children) == 0 and attrs.get("width") == "0":
            remove_element(node, parent_node); return
        if rectHeight0 and rectWidth0 and node.name == "rect" and len(node.children) == 0 and attrs.get("height") == "0":
            remove_element(node, parent_node); return
        if patternWidth0 and node.name == "pattern" and attrs.get("width") == "0":
            remove_element(node, parent_node); return
        if patternHeight0 and node.name == "pattern" and attrs.get("height") == "0":
            remove_element(node, parent_node); return
        if imageWidth0 and node.name == "image" and attrs.get("width") == "0":
            remove_element(node, parent_node); return
        if imageHeight0 and node.name == "image" and attrs.get("height") == "0":
            remove_element(node, parent_node); return
        if polylineEmptyPoints and node.name == "polyline" and attrs.get("points") is None:
            remove_element(node, parent_node); return
        if polygonEmptyPoints and node.name == "polygon" and attrs.get("points") is None:
            remove_element(node, parent_node); return

        computed = compute_style(stylesheet, node)
        vis = computed.get("visibility")
        if (
            isHidden
            and vis
            and vis["type"] == "static"
            and vis.get("value") == "hidden"
            and query_selector(node, "[visibility=visible]") is None
        ):
            remove_element(node, parent_node); return

        disp = computed.get("display")
        if (
            displayNone
            and disp
            and disp["type"] == "static"
            and disp.get("value") == "none"
            and node.name != "marker"
        ):
            remove_element(node, parent_node); return

        if pathEmptyD and node.name == "path":
            if attrs.get("d") is None:
                remove_element(node, parent_node); return
            path_data = parse_path_data(attrs["d"])
            if len(path_data) == 0:
                remove_element(node, parent_node); return
            if (
                len(path_data) == 1
                and computed.get("marker-start") is None
                and computed.get("marker-end") is None
            ):
                remove_element(node, parent_node); return

        for attr_name, value in node.attributes.items():
            for id_ in find_references(attr_name, value):
                all_references.add(id_)

    def root_exit(node, parent_node):
        for id_ in removed_def_ids:
            refs = references_by_id.get(id_)
            if refs:
                for use_node, use_parent in refs:
                    detach_node_from_parent(use_node, use_parent)

        if not state["deoptimized"]:
            for nr_node, nr_parent in list(non_rendered_nodes.items()):
                if can_remove_non_rendering_node(nr_node):
                    detach_node_from_parent(nr_node, nr_parent)

        for def_node, def_parent in list(all_defs.items()):
            if len(def_node.children) == 0:
                detach_node_from_parent(def_node, def_parent)

    return {
        "element": {"enter": enter},
        "root": {"exit": root_exit},
    }
