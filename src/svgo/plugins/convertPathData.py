import math

from ..collections import pathElems
from ..pathutil import js2path, path2js
from ..style import collect_stylesheet, compute_style
from ..tools import cleanup_out_data, to_fixed, _js_round
from ..visit import visit
from .applyTransforms import applyTransforms

name = "convertPathData"
description = "optimizes path data: writes in shorter form, applies transformations"


class _Ctx:
    precision = 3
    error = 0.0
    arc_threshold = 2.5
    arc_tolerance = 0.5

    @staticmethod
    def round_data(data):
        return data


_ctx = _Ctx()


def _strong_round(data):
    precision_num = _ctx.precision or 0
    i = len(data) - 1
    while i >= 0:
        fixed = to_fixed(data[i], precision_num)
        if fixed != data[i]:
            rounded = to_fixed(data[i], precision_num - 1)
            data[i] = fixed if to_fixed(abs(rounded - data[i]), precision_num + 1) >= _ctx.error else rounded
        i -= 1
    return data


def _round(data):
    i = len(data) - 1
    while i >= 0:
        data[i] = _js_round(data[i])
        i -= 1
    return data


def _at(arr, i):
    """JS array indexing: out-of-range (including negative) -> NaN."""
    if 0 <= i < len(arr):
        return arr[i]
    return float("nan")


def _js_filter(arr, cb):
    """ECMAScript Array.prototype.filter semantics: length captured once, each
    element read fresh (so in-callback splices are observed)."""
    result = []
    length = len(arr)
    k = 0
    while k < length:
        if k < len(arr):
            k_value = arr[k]
            if cb(k_value, k, arr):
                result.append(k_value)
        k += 1
    return result


def fn(root, params, info):
    _applyTransforms = params.get("applyTransforms", True)
    applyTransformsStroked = params.get("applyTransformsStroked", True)
    makeArcs = params.get("makeArcs", {"threshold": 2.5, "tolerance": 0.5})
    straightCurves = params.get("straightCurves", True)
    convertToQ = params.get("convertToQ", True)
    lineShorthands = params.get("lineShorthands", True)
    convertToZ = params.get("convertToZ", True)
    curveSmoothShorthands = params.get("curveSmoothShorthands", True)
    floatPrecision = params.get("floatPrecision", 3)
    transformPrecision = params.get("transformPrecision", 5)
    smartArcRounding = params.get("smartArcRounding", True)
    removeUseless = params.get("removeUseless", True)
    collapseRepeated = params.get("collapseRepeated", True)
    utilizeAbsolute = params.get("utilizeAbsolute", True)
    leadingZero = params.get("leadingZero", True)
    negativeExtraSpace = params.get("negativeExtraSpace", True)
    noSpaceAfterFlags = params.get("noSpaceAfterFlags", False)
    forceAbsolutePath = params.get("forceAbsolutePath", False)

    new_params = {
        "applyTransforms": _applyTransforms,
        "applyTransformsStroked": applyTransformsStroked,
        "makeArcs": makeArcs,
        "straightCurves": straightCurves,
        "convertToQ": convertToQ,
        "lineShorthands": lineShorthands,
        "convertToZ": convertToZ,
        "curveSmoothShorthands": curveSmoothShorthands,
        "floatPrecision": floatPrecision,
        "transformPrecision": transformPrecision,
        "smartArcRounding": smartArcRounding,
        "removeUseless": removeUseless,
        "collapseRepeated": collapseRepeated,
        "utilizeAbsolute": utilizeAbsolute,
        "leadingZero": leadingZero,
        "negativeExtraSpace": negativeExtraSpace,
        "noSpaceAfterFlags": noSpaceAfterFlags,
        "forceAbsolutePath": forceAbsolutePath,
    }

    if _applyTransforms:
        visit(root, applyTransforms(root, {
            "transformPrecision": transformPrecision,
            "applyTransformsStroked": applyTransformsStroked,
        }))

    stylesheet = collect_stylesheet(root)

    def enter(node):
        if node.name in pathElems and node.attributes.get("d") is not None:
            computed = compute_style(stylesheet, node)
            _ctx.precision = floatPrecision
            if floatPrecision is not False:
                _ctx.error = to_fixed_pow(floatPrecision)
            else:
                _ctx.error = 1e-2
            if floatPrecision and floatPrecision > 0 and floatPrecision < 20:
                _ctx.round_data = _strong_round
            else:
                _ctx.round_data = _round
            if makeArcs:
                _ctx.arc_threshold = makeArcs["threshold"]
                _ctx.arc_tolerance = makeArcs["tolerance"]
            has_marker_mid = computed.get("marker-mid") is not None

            stroke_style = computed.get("stroke")
            maybe_has_stroke = stroke_style and (
                stroke_style["type"] == "dynamic" or stroke_style.get("value") != "none"
            )
            linecap_style = computed.get("stroke-linecap")
            maybe_has_linecap = linecap_style and (
                linecap_style["type"] == "dynamic" or linecap_style.get("value") != "butt"
            )
            if maybe_has_stroke:
                linejoin_style = computed.get("stroke-linejoin")
                is_safe_to_use_z = (
                    linecap_style is not None
                    and linecap_style["type"] == "static"
                    and linecap_style.get("value") == "round"
                    and linejoin_style is not None
                    and linejoin_style["type"] == "static"
                    and linejoin_style.get("value") == "round"
                )
            else:
                is_safe_to_use_z = True

            def is_safe_to_remove(is_first_draw, safe_if_not_first_draw):
                if not maybe_has_stroke:
                    return True
                if is_first_draw:
                    return not maybe_has_linecap
                return safe_if_not_first_draw

            data = path2js(node)

            if len(data):
                includes_vertices = any(item["command"] not in ("m", "M") for item in data)
                _convert_to_relative(data)
                data = _filters(data, new_params, is_safe_to_use_z, is_safe_to_remove, has_marker_mid)
                if utilizeAbsolute:
                    data = _convert_to_mixed(data, new_params)

                has_marker = (
                    node.attributes.get("marker-start") is not None
                    or node.attributes.get("marker-end") is not None
                )
                is_markers_only_path = (
                    has_marker
                    and includes_vertices
                    and all(item["command"] in ("m", "M") for item in data)
                )
                if is_markers_only_path:
                    data.append({"command": "z", "args": []})

                js2path(node, data, new_params)

    return {"element": {"enter": lambda node, parent_node: enter(node)}}


def to_fixed_pow(precision):
    from ..tools import js_to_fixed

    return js_to_fixed(math.pow(0.1, precision), precision)


def _convert_to_relative(path_data):
    start = [0.0, 0.0]
    cursor = [0.0, 0.0]
    prev_coords = [0.0, 0.0]

    for i in range(len(path_data)):
        path_item = path_data[i]
        command = path_item["command"]
        args = path_item["args"]

        if command == "m":
            cursor[0] += args[0]; cursor[1] += args[1]
            start[0] = cursor[0]; start[1] = cursor[1]
        elif command == "M":
            if i != 0:
                command = "m"
            args[0] -= cursor[0]; args[1] -= cursor[1]
            cursor[0] += args[0]; cursor[1] += args[1]
            start[0] = cursor[0]; start[1] = cursor[1]
        elif command == "l":
            cursor[0] += args[0]; cursor[1] += args[1]
        elif command == "L":
            command = "l"
            args[0] -= cursor[0]; args[1] -= cursor[1]
            cursor[0] += args[0]; cursor[1] += args[1]
        elif command == "h":
            cursor[0] += args[0]
        elif command == "H":
            command = "h"
            args[0] -= cursor[0]; cursor[0] += args[0]
        elif command == "v":
            cursor[1] += args[0]
        elif command == "V":
            command = "v"
            args[0] -= cursor[1]; cursor[1] += args[0]
        elif command == "c":
            cursor[0] += args[4]; cursor[1] += args[5]
        elif command == "C":
            command = "c"
            args[0] -= cursor[0]; args[1] -= cursor[1]
            args[2] -= cursor[0]; args[3] -= cursor[1]
            args[4] -= cursor[0]; args[5] -= cursor[1]
            cursor[0] += args[4]; cursor[1] += args[5]
        elif command == "s":
            cursor[0] += args[2]; cursor[1] += args[3]
        elif command == "S":
            command = "s"
            args[0] -= cursor[0]; args[1] -= cursor[1]
            args[2] -= cursor[0]; args[3] -= cursor[1]
            cursor[0] += args[2]; cursor[1] += args[3]
        elif command == "q":
            cursor[0] += args[2]; cursor[1] += args[3]
        elif command == "Q":
            command = "q"
            args[0] -= cursor[0]; args[1] -= cursor[1]
            args[2] -= cursor[0]; args[3] -= cursor[1]
            cursor[0] += args[2]; cursor[1] += args[3]
        elif command == "t":
            cursor[0] += args[0]; cursor[1] += args[1]
        elif command == "T":
            command = "t"
            args[0] -= cursor[0]; args[1] -= cursor[1]
            cursor[0] += args[0]; cursor[1] += args[1]
        elif command == "a":
            cursor[0] += args[5]; cursor[1] += args[6]
        elif command == "A":
            command = "a"
            args[5] -= cursor[0]; args[6] -= cursor[1]
            cursor[0] += args[5]; cursor[1] += args[6]
        elif command == "Z" or command == "z":
            cursor[0] = start[0]; cursor[1] = start[1]

        path_item["command"] = command
        path_item["args"] = args
        path_item["base"] = prev_coords
        path_item["coords"] = [cursor[0], cursor[1]]
        prev_coords = path_item["coords"]

    return path_data


def _data2path(params, path_data):
    out = ""
    for item in path_data:
        str_data = ""
        if item.get("args") is not None:
            str_data = cleanup_out_data(_ctx.round_data(list(item["args"])), params)
        out += item["command"] + str_data
    return out


def _filters(path, params, is_safe_to_use_z, is_safe_to_remove, has_marker_mid):
    rel_subpoint = [0.0, 0.0]
    path_base = [0.0, 0.0]
    state = {"prev": {}, "prev_q_control_point": None}

    def stringify(data):
        return _data2path(params, data)

    def cb(item, index, path):
        prev = state["prev"]
        q_control_point = state["prev_q_control_point"]
        command = item["command"]
        data = item["args"]
        next_item = path[index + 1] if index + 1 < len(path) else None

        if command != "Z" and command != "z":
            sdata = data
            if command == "s":
                sdata = [0, 0] + list(data)
                pdata = prev["args"]
                n = len(pdata)
                # JS array out-of-bounds (incl. negative) yields undefined -> NaN
                sdata[0] = _at(pdata, n - 2) - _at(pdata, n - 4)
                sdata[1] = _at(pdata, n - 1) - _at(pdata, n - 3)

            circle = None
            if params["makeArcs"] and (command == "c" or command == "s") and _is_convex(sdata):
                circle = _find_circle(sdata)
            if circle:
                r = _ctx.round_data([circle["radius"]])[0]
                angle = _find_arc_angle(sdata, circle)
                sweep = 1 if (sdata[5] * sdata[0] - sdata[4] * sdata[1] > 0) else 0
                arc = {
                    "command": "a",
                    "args": [r, r, 0, 0, sweep, sdata[4], sdata[5]],
                    "coords": list(item["coords"]),
                    "base": item["base"],
                }
                output = [arc]
                rel_center = [circle["center"][0] - sdata[4], circle["center"][1] - sdata[5]]
                rel_circle = {"center": rel_center, "radius": circle["radius"]}
                arc_curves = [item]
                has_prev = 0
                suffix = ""
                next_longhand = None

                if (
                    (prev.get("command") == "c" and _is_convex(prev["args"]) and _is_arc_prev(prev["args"], circle))
                    or (prev.get("command") == "a" and prev.get("sdata") and _is_arc_prev(prev["sdata"], circle))
                ):
                    arc_curves.insert(0, prev)
                    arc["base"] = prev["base"]
                    arc["args"][5] = arc["coords"][0] - arc["base"][0]
                    arc["args"][6] = arc["coords"][1] - arc["base"][1]
                    prev_data = prev["sdata"] if prev.get("command") == "a" else prev["args"]
                    prev_angle = _find_arc_angle(prev_data, {
                        "center": [prev_data[4] + circle["center"][0], prev_data[5] + circle["center"][1]],
                        "radius": circle["radius"],
                    })
                    angle += prev_angle
                    if angle > math.pi:
                        arc["args"][3] = 1
                    has_prev = 1

                j = index
                while True:
                    j += 1
                    next_item = path[j] if j < len(path) else None
                    if not (next_item and (next_item["command"] == "c" or next_item["command"] == "s")):
                        break
                    next_data = next_item["args"]
                    if next_item["command"] == "s":
                        next_longhand = _make_longhand(
                            {"command": "s", "args": list(next_item["args"])}, path[j - 1]["args"]
                        )
                        next_data = next_longhand["args"]
                        next_longhand["args"] = next_data[0:2]
                        suffix = stringify([next_longhand])
                    if _is_convex(next_data) and _is_arc(next_data, rel_circle):
                        angle += _find_arc_angle(next_data, rel_circle)
                        if angle - 2 * math.pi > 1e-3:
                            break
                        if angle > math.pi:
                            arc["args"][3] = 1
                        arc_curves.append(next_item)
                        if 2 * math.pi - angle > 1e-3:
                            arc["coords"] = next_item["coords"]
                            arc["args"][5] = arc["coords"][0] - arc["base"][0]
                            arc["args"][6] = arc["coords"][1] - arc["base"][1]
                        else:
                            arc["args"][5] = 2 * (rel_circle["center"][0] - next_data[4])
                            arc["args"][6] = 2 * (rel_circle["center"][1] - next_data[5])
                            arc["coords"] = [arc["base"][0] + arc["args"][5], arc["base"][1] + arc["args"][6]]
                            arc = {
                                "command": "a",
                                "args": [r, r, 0, 0, sweep,
                                         next_item["coords"][0] - arc["coords"][0],
                                         next_item["coords"][1] - arc["coords"][1]],
                                "coords": next_item["coords"],
                                "base": arc["coords"],
                            }
                            output.append(arc)
                            j += 1
                            break
                        rel_center[0] -= next_data[4]
                        rel_center[1] -= next_data[5]
                    else:
                        break

                if len(stringify(output) + suffix) < len(stringify(arc_curves)):
                    if j < len(path) and path[j]["command"] == "s":
                        _make_longhand(path[j], path[j - 1]["args"])
                    if has_prev:
                        prev_arc = output.pop(0)
                        _ctx.round_data(prev_arc["args"])
                        rel_subpoint[0] += prev_arc["args"][5] - prev["args"][len(prev["args"]) - 2]
                        rel_subpoint[1] += prev_arc["args"][6] - prev["args"][len(prev["args"]) - 1]
                        prev["command"] = "a"
                        prev["args"] = prev_arc["args"]
                        item["base"] = prev_arc["coords"]
                        prev["coords"] = prev_arc["coords"]
                    arc = output.pop(0) if output else None
                    if len(arc_curves) == 1:
                        item["sdata"] = list(sdata)
                    elif len(arc_curves) - 1 - has_prev > 0:
                        count = len(arc_curves) - 1 - has_prev
                        path[index + 1:index + 1 + count] = output
                    if not arc:
                        return False
                    command = "a"
                    data = arc["args"]
                    item["coords"] = arc["coords"]

            if _ctx.precision is not False:
                if command in ("m", "l", "t", "q", "s", "c"):
                    for k in range(len(data) - 1, -1, -1):
                        data[k] += item["base"][k % 2] - rel_subpoint[k % 2]
                elif command == "h":
                    data[0] += item["base"][0] - rel_subpoint[0]
                elif command == "v":
                    data[0] += item["base"][1] - rel_subpoint[1]
                elif command == "a":
                    data[5] += item["base"][0] - rel_subpoint[0]
                    data[6] += item["base"][1] - rel_subpoint[1]
                _ctx.round_data(data)

                if command == "h":
                    rel_subpoint[0] += data[0]
                elif command == "v":
                    rel_subpoint[1] += data[0]
                else:
                    rel_subpoint[0] += data[len(data) - 2]
                    rel_subpoint[1] += data[len(data) - 1]
                _ctx.round_data(rel_subpoint)

                if command == "M" or command == "m":
                    path_base[0] = rel_subpoint[0]
                    path_base[1] = rel_subpoint[1]

            sagitta = _calculate_sagitta(data) if command == "a" else None
            if params["smartArcRounding"] and sagitta is not None and _ctx.precision:
                precision_new = _ctx.precision
                while precision_new >= 0:
                    radius = to_fixed(data[0], precision_new)
                    sagitta_new = _calculate_sagitta([radius, radius] + list(data[2:]))
                    if sagitta_new is not None and abs(sagitta - sagitta_new) < _ctx.error:
                        data[0] = radius
                        data[1] = radius
                    else:
                        break
                    precision_new -= 1

            if params["straightCurves"]:
                if (command == "c" and _is_curve_straight_line(data)) or (
                    command == "s" and _is_curve_straight_line(sdata)
                ):
                    if next_item and next_item["command"] == "s":
                        _make_longhand(next_item, data)
                    command = "l"
                    data = data[-2:]
                elif (command == "q" and _is_curve_straight_line(data)) or (
                    command == "t" and prev.get("command") != "q" and prev.get("command") != "t"
                ):
                    if command == "q" and next_item and next_item["command"] == "t":
                        _make_longhand(next_item, data)
                    if command == "t" and next_item and next_item["command"] == "t":
                        next_item["command"] = "q"
                        next_item["args"][0:0] = [
                            (2 * item["coords"][0] - item["base"][0]) - item["coords"][0],
                            (2 * item["coords"][1] - item["base"][1]) - item["coords"][1],
                        ]
                    command = "l"
                    data = data[-2:]
                elif command == "a" and (
                    data[0] == 0 or data[1] == 0 or (sagitta is not None and sagitta < _ctx.error)
                ):
                    command = "l"
                    data = data[-2:]

            if params["convertToQ"] and command == "c":
                x1 = 0.75 * (item["base"][0] + data[0]) - 0.25 * item["base"][0]
                x2 = 0.75 * (item["base"][0] + data[2]) - 0.25 * (item["base"][0] + data[4])
                if abs(x1 - x2) < _ctx.error * 2:
                    y1 = 0.75 * (item["base"][1] + data[1]) - 0.25 * item["base"][1]
                    y2 = 0.75 * (item["base"][1] + data[3]) - 0.25 * (item["base"][1] + data[5])
                    if abs(y1 - y2) < _ctx.error * 2:
                        new_data = list(data)
                        new_data[0:4] = [x1 + x2 - item["base"][0], y1 + y2 - item["base"][1]]
                        _ctx.round_data(new_data)
                        original_length = len(cleanup_out_data(data, params))
                        new_length = len(cleanup_out_data(new_data, params))
                        if new_length < original_length:
                            command = "q"
                            data = new_data
                            if next_item and next_item["command"] == "s":
                                _make_longhand(next_item, data)

            if params["lineShorthands"] and command == "l":
                if data[1] == 0:
                    command = "h"
                    data = data[:-1]
                elif data[0] == 0:
                    command = "v"
                    data = data[1:]

            if (
                params["collapseRepeated"]
                and has_marker_mid is False
                and command in ("m", "h", "v")
                and prev.get("command")
                and command == prev["command"].lower()
                and (
                    (command != "h" and command != "v")
                    or ((prev["args"][0] >= 0) == (data[0] >= 0))
                )
            ):
                prev["args"][0] += data[0]
                if command != "h" and command != "v":
                    prev["args"][1] += data[1]
                prev["coords"] = item["coords"]
                path[index] = prev
                return False

            if params["curveSmoothShorthands"] and prev.get("command"):
                if command == "c":
                    if (
                        prev["command"] == "c"
                        and abs(data[0] - -(prev["args"][2] - prev["args"][4])) < _ctx.error
                        and abs(data[1] - -(prev["args"][3] - prev["args"][5])) < _ctx.error
                    ):
                        command = "s"; data = data[2:]
                    elif (
                        prev["command"] == "s"
                        and abs(data[0] - -(prev["args"][0] - prev["args"][2])) < _ctx.error
                        and abs(data[1] - -(prev["args"][1] - prev["args"][3])) < _ctx.error
                    ):
                        command = "s"; data = data[2:]
                    elif (
                        prev["command"] != "c"
                        and prev["command"] != "s"
                        and abs(data[0]) < _ctx.error
                        and abs(data[1]) < _ctx.error
                    ):
                        command = "s"; data = data[2:]
                elif command == "q":
                    if (
                        prev["command"] == "q"
                        and abs(data[0] - (prev["args"][2] - prev["args"][0])) < _ctx.error
                        and abs(data[1] - (prev["args"][3] - prev["args"][1])) < _ctx.error
                    ):
                        command = "t"; data = data[2:]
                    elif prev["command"] == "t":
                        predicted = _reflect_point(q_control_point, item["base"])
                        real = [data[0] + item["base"][0], data[1] + item["base"][1]]
                        if abs(predicted[0] - real[0]) < _ctx.error and abs(predicted[1] - real[1]) < _ctx.error:
                            command = "t"; data = data[2:]

            if params["removeUseless"] and is_safe_to_remove(
                prev.get("command") == "m" or prev.get("command") == "M", True
            ):
                if command in ("l", "h", "v", "q", "t", "c", "s") and all(x == 0 for x in data):
                    path[index] = prev
                    return False
                if command == "a" and data[5] == 0 and data[6] == 0:
                    path[index] = prev
                    return False

            if (
                params["convertToZ"]
                and (is_safe_to_use_z or (next_item and next_item["command"] in ("Z", "z")))
                and command in ("l", "h", "v")
            ):
                if abs(path_base[0] - item["coords"][0]) < _ctx.error and abs(path_base[1] - item["coords"][1]) < _ctx.error:
                    command = "z"
                    data = []

            item["command"] = command
            item["args"] = data
        else:
            rel_subpoint[0] = path_base[0]
            rel_subpoint[1] = path_base[1]
            if prev.get("command") == "Z" or prev.get("command") == "z":
                return False

        if (
            (command == "Z" or command == "z")
            and params["removeUseless"]
            and is_safe_to_remove(prev.get("command") == "m" or prev.get("command") == "M", is_safe_to_use_z)
            and abs(item["base"][0] - item["coords"][0]) < _ctx.error / 10
            and abs(item["base"][1] - item["coords"][1]) < _ctx.error / 10
        ):
            return False

        if command == "q":
            state["prev_q_control_point"] = [data[0] + item["base"][0], data[1] + item["base"][1]]
        elif command == "t":
            if q_control_point:
                state["prev_q_control_point"] = _reflect_point(q_control_point, item["base"])
            else:
                state["prev_q_control_point"] = item["coords"]
        else:
            state["prev_q_control_point"] = None
        state["prev"] = item
        return True

    return _js_filter(path, cb)


def _convert_to_mixed(path, params):
    state = {"prev": path[0]}

    def cb(item, index, arr):
        if index == 0:
            return True
        if item["command"] == "Z" or item["command"] == "z":
            state["prev"] = item
            return True

        command = item["command"]
        data = item["args"]
        adata = list(data)
        rdata = list(data)

        if command in ("m", "l", "t", "q", "s", "c"):
            for i in range(len(adata) - 1, -1, -1):
                adata[i] += item["base"][i % 2]
        elif command == "h":
            adata[0] += item["base"][0]
        elif command == "v":
            adata[0] += item["base"][1]
        elif command == "a":
            adata[5] += item["base"][0]
            adata[6] += item["base"][1]

        _ctx.round_data(adata)
        _ctx.round_data(rdata)

        absolute_str = cleanup_out_data(adata, params)
        relative_str = cleanup_out_data(rdata, params)
        prev = state["prev"]

        if params["forceAbsolutePath"] or (
            len(absolute_str) < len(relative_str)
            and not (
                params["negativeExtraSpace"]
                and command == prev["command"]
                and ord(prev["command"][0]) > 96
                and len(absolute_str) == len(relative_str) - 1
                and (
                    data[0] < 0
                    or (math.floor(data[0]) == 0 and not float(data[0]).is_integer() and (prev["args"][len(prev["args"]) - 1] % 1))
                )
            )
        ):
            item["command"] = command.upper()
            item["args"] = adata

        state["prev"] = item
        return True

    return _js_filter(path, cb)


def _is_convex(data):
    center = _get_intersection([0, 0, data[2], data[3], data[0], data[1], data[4], data[5]])
    return (
        center is not None
        and (data[2] < center[0]) == (center[0] < 0)
        and (data[3] < center[1]) == (center[1] < 0)
        and (data[4] < center[0]) == (center[0] < data[0])
        and (data[5] < center[1]) == (center[1] < data[1])
    )


def _get_intersection(coords):
    a1 = coords[1] - coords[3]
    b1 = coords[2] - coords[0]
    c1 = coords[0] * coords[3] - coords[2] * coords[1]
    a2 = coords[5] - coords[7]
    b2 = coords[6] - coords[4]
    c2 = coords[4] * coords[7] - coords[5] * coords[6]
    denom = a1 * b2 - a2 * b1
    if not denom:
        return None
    cross = [(b1 * c2 - b2 * c1) / denom, (a1 * c2 - a2 * c1) / -denom]
    if (
        not math.isnan(cross[0])
        and not math.isnan(cross[1])
        and math.isfinite(cross[0])
        and math.isfinite(cross[1])
    ):
        return cross
    return None


def _is_curve_straight_line(data):
    i = len(data) - 2
    a = -data[i + 1]
    b = data[i]
    denom = a * a + b * b
    if i <= 1 or denom == 0 or not math.isfinite(1 / denom):
        return False
    d = 1 / denom
    i -= 2
    while i >= 0:
        if math.sqrt((a * data[i] + b * data[i + 1]) ** 2 * d) > _ctx.error:
            return False
        i -= 2
    return True


def _calculate_sagitta(data):
    if data[3] == 1:
        return None
    rx = data[0]
    ry = data[1]
    if abs(rx - ry) > _ctx.error:
        return None
    chord = math.hypot(data[5], data[6])
    if chord > rx * 2:
        return None
    return rx - math.sqrt(rx ** 2 - 0.25 * chord ** 2)


def _make_longhand(item, data):
    if item["command"] == "s":
        item["command"] = "c"
    elif item["command"] == "t":
        item["command"] = "q"
    item["args"][0:0] = [
        data[len(data) - 2] - data[len(data) - 4],
        data[len(data) - 1] - data[len(data) - 3],
    ]
    return item


def _get_distance(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def _reflect_point(control_point, base):
    return [2 * base[0] - control_point[0], 2 * base[1] - control_point[1]]


def _get_cubic_bezier_point(curve, t):
    sqr_t = t * t
    cub_t = sqr_t * t
    mt = 1 - t
    sqr_mt = mt * mt
    return [
        3 * sqr_mt * t * curve[0] + 3 * mt * sqr_t * curve[2] + cub_t * curve[4],
        3 * sqr_mt * t * curve[1] + 3 * mt * sqr_t * curve[3] + cub_t * curve[5],
    ]


def _find_circle(curve):
    mid_point = _get_cubic_bezier_point(curve, 1 / 2)
    m1 = [mid_point[0] / 2, mid_point[1] / 2]
    m2 = [(mid_point[0] + curve[4]) / 2, (mid_point[1] + curve[5]) / 2]
    center = _get_intersection([
        m1[0], m1[1], m1[0] + m1[1], m1[1] - m1[0],
        m2[0], m2[1], m2[0] + (m2[1] - mid_point[1]), m2[1] - (m2[0] - mid_point[0]),
    ])
    radius = _get_distance([0, 0], center) if center else None
    if center is None:
        return None
    tolerance = min(_ctx.arc_threshold * _ctx.error, (_ctx.arc_tolerance * radius) / 100)
    if radius < 1e15 and all(
        abs(_get_distance(_get_cubic_bezier_point(curve, point), center) - radius) <= tolerance
        for point in (1 / 4, 3 / 4)
    ):
        return {"center": center, "radius": radius}
    return None


def _is_arc(curve, circle):
    tolerance = min(_ctx.arc_threshold * _ctx.error, (_ctx.arc_tolerance * circle["radius"]) / 100)
    return all(
        abs(_get_distance(_get_cubic_bezier_point(curve, point), circle["center"]) - circle["radius"]) <= tolerance
        for point in (0, 1 / 4, 1 / 2, 3 / 4, 1)
    )


def _is_arc_prev(curve, circle):
    return _is_arc(curve, {
        "center": [circle["center"][0] + curve[4], circle["center"][1] + curve[5]],
        "radius": circle["radius"],
    })


def _find_arc_angle(curve, rel_circle):
    x1 = -rel_circle["center"][0]
    y1 = -rel_circle["center"][1]
    x2 = curve[4] - rel_circle["center"][0]
    y2 = curve[5] - rel_circle["center"][1]
    val = (x1 * x2 + y1 * y2) / math.sqrt((x1 * x1 + y1 * y1) * (x2 * x2 + y2 * y2))
    val = max(-1.0, min(1.0, val))
    return math.acos(val)
