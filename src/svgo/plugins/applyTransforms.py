import math
import re

from ..collections import attrsGroupsDefaults, referencesProps
from ..pathutil import path2js
from ..style import collect_stylesheet, compute_style
from ..tools import includes_url_reference, js_to_fixed, remove_leading_zero
from ..transforms import transform2js, transform_arc, transforms_multiply

name = "applyTransforms"
description = "applies transforms to path data"

_reg_numeric = re.compile(r"[-+]?(\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def applyTransforms(root, params):
    """Returns a visitor (not registered as a standalone default-preset plugin;
    invoked internally by convertPathData)."""
    stylesheet = collect_stylesheet(root)

    def enter(node, parent_node=None):
        if node.attributes.get("d") is None:
            return
        if node.attributes.get("id") is not None:
            return
        if (
            node.attributes.get("transform") is None
            or node.attributes.get("transform") == ""
            or node.attributes.get("style") is not None
            or any(
                nm in referencesProps and includes_url_reference(val)
                for nm, val in node.attributes.items()
            )
        ):
            return

        computed = compute_style(stylesheet, node)
        transform_style = computed.get("transform")
        if (
            transform_style is not None
            and transform_style["type"] == "static"
            and transform_style.get("value") != node.attributes["transform"]
        ):
            return

        matrix = transforms_multiply(transform2js(node.attributes["transform"]))

        stroke_style = computed.get("stroke")
        stroke = stroke_style["value"] if (stroke_style and stroke_style["type"] == "static") else None
        sw_style = computed.get("stroke-width")
        stroke_width = sw_style["value"] if (sw_style and sw_style["type"] == "static") else None
        transform_precision = params["transformPrecision"]

        if (stroke_style and stroke_style["type"] == "dynamic") or (
            sw_style and sw_style["type"] == "dynamic"
        ):
            return

        scale = js_to_fixed(math.hypot(matrix["data"][0], matrix["data"][1]), transform_precision)

        if stroke and stroke != "none":
            if not params["applyTransformsStroked"]:
                return
            if (
                matrix["data"][0] != matrix["data"][3] or matrix["data"][1] != -matrix["data"][2]
            ) and (
                matrix["data"][0] != -matrix["data"][3] or matrix["data"][1] != matrix["data"][2]
            ):
                return
            if scale != 1:
                if node.attributes.get("vector-effect") != "non-scaling-stroke":
                    base_sw = stroke_width or attrsGroupsDefaults["presentation"]["stroke-width"]

                    def scale_num(m):
                        return remove_leading_zero(float(m.group(0)) * scale)

                    node.attributes["stroke-width"] = _reg_numeric.sub(scale_num, base_sw.strip())
                    if node.attributes.get("stroke-dashoffset") is not None:
                        node.attributes["stroke-dashoffset"] = _reg_numeric.sub(
                            scale_num, node.attributes["stroke-dashoffset"].strip()
                        )
                    if node.attributes.get("stroke-dasharray") is not None:
                        node.attributes["stroke-dasharray"] = _reg_numeric.sub(
                            scale_num, node.attributes["stroke-dasharray"].strip()
                        )

        path_data = path2js(node)
        _apply_matrix_to_path_data(path_data, matrix["data"])
        del node.attributes["transform"]

    return {"element": {"enter": enter}}


def _transform_absolute_point(matrix, x, y):
    return [matrix[0] * x + matrix[2] * y + matrix[4], matrix[1] * x + matrix[3] * y + matrix[5]]


def _transform_relative_point(matrix, x, y):
    return [matrix[0] * x + matrix[2] * y, matrix[1] * x + matrix[3] * y]


def _apply_matrix_to_path_data(path_data, matrix):
    start = [0.0, 0.0]
    cursor = [0.0, 0.0]

    for path_item in path_data:
        command = path_item["command"]
        args = path_item["args"]

        if command == "M":
            cursor[0] = args[0]; cursor[1] = args[1]
            start[0] = cursor[0]; start[1] = cursor[1]
            x, y = _transform_absolute_point(matrix, args[0], args[1])
            args[0] = x; args[1] = y
        if command == "m":
            cursor[0] += args[0]; cursor[1] += args[1]
            start[0] = cursor[0]; start[1] = cursor[1]
            x, y = _transform_relative_point(matrix, args[0], args[1])
            args[0] = x; args[1] = y

        if command == "H":
            command = "L"; args = [args[0], cursor[1]]
        if command == "h":
            command = "l"; args = [args[0], 0]
        if command == "V":
            command = "L"; args = [cursor[0], args[0]]
        if command == "v":
            command = "l"; args = [0, args[0]]

        if command == "L":
            cursor[0] = args[0]; cursor[1] = args[1]
            x, y = _transform_absolute_point(matrix, args[0], args[1])
            args[0] = x; args[1] = y
        if command == "l":
            cursor[0] += args[0]; cursor[1] += args[1]
            x, y = _transform_relative_point(matrix, args[0], args[1])
            args[0] = x; args[1] = y

        if command == "C":
            cursor[0] = args[4]; cursor[1] = args[5]
            x1, y1 = _transform_absolute_point(matrix, args[0], args[1])
            x2, y2 = _transform_absolute_point(matrix, args[2], args[3])
            x, y = _transform_absolute_point(matrix, args[4], args[5])
            args[0], args[1], args[2], args[3], args[4], args[5] = x1, y1, x2, y2, x, y
        if command == "c":
            cursor[0] += args[4]; cursor[1] += args[5]
            x1, y1 = _transform_relative_point(matrix, args[0], args[1])
            x2, y2 = _transform_relative_point(matrix, args[2], args[3])
            x, y = _transform_relative_point(matrix, args[4], args[5])
            args[0], args[1], args[2], args[3], args[4], args[5] = x1, y1, x2, y2, x, y

        if command == "S":
            cursor[0] = args[2]; cursor[1] = args[3]
            x2, y2 = _transform_absolute_point(matrix, args[0], args[1])
            x, y = _transform_absolute_point(matrix, args[2], args[3])
            args[0], args[1], args[2], args[3] = x2, y2, x, y
        if command == "s":
            cursor[0] += args[2]; cursor[1] += args[3]
            x2, y2 = _transform_relative_point(matrix, args[0], args[1])
            x, y = _transform_relative_point(matrix, args[2], args[3])
            args[0], args[1], args[2], args[3] = x2, y2, x, y

        if command == "Q":
            cursor[0] = args[2]; cursor[1] = args[3]
            x1, y1 = _transform_absolute_point(matrix, args[0], args[1])
            x, y = _transform_absolute_point(matrix, args[2], args[3])
            args[0], args[1], args[2], args[3] = x1, y1, x, y
        if command == "q":
            cursor[0] += args[2]; cursor[1] += args[3]
            x1, y1 = _transform_relative_point(matrix, args[0], args[1])
            x, y = _transform_relative_point(matrix, args[2], args[3])
            args[0], args[1], args[2], args[3] = x1, y1, x, y

        if command == "T":
            cursor[0] = args[0]; cursor[1] = args[1]
            x, y = _transform_absolute_point(matrix, args[0], args[1])
            args[0] = x; args[1] = y
        if command == "t":
            cursor[0] += args[0]; cursor[1] += args[1]
            x, y = _transform_relative_point(matrix, args[0], args[1])
            args[0] = x; args[1] = y

        if command == "A":
            transform_arc(cursor, args, matrix)
            cursor[0] = args[5]; cursor[1] = args[6]
            if abs(args[2]) > 80:
                a = args[0]; rotation = args[2]
                args[0] = args[1]; args[1] = a
                args[2] = rotation + (-90 if rotation > 0 else 90)
            x, y = _transform_absolute_point(matrix, args[5], args[6])
            args[5] = x; args[6] = y
        if command == "a":
            transform_arc([0, 0], args, matrix)
            cursor[0] += args[5]; cursor[1] += args[6]
            if abs(args[2]) > 80:
                a = args[0]; rotation = args[2]
                args[0] = args[1]; args[1] = a
                args[2] = rotation + (-90 if rotation > 0 else 90)
            x, y = _transform_relative_point(matrix, args[5], args[6])
            args[5] = x; args[6] = y

        if command == "z" or command == "Z":
            cursor[0] = start[0]; cursor[1] = start[1]

        path_item["command"] = command
        path_item["args"] = args
