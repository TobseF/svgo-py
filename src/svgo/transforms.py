"""Transform math. Port of ``plugins/_transforms.js``.

A transform item is a dict ``{"name": str, "data": [float, ...]}``.
"""

from __future__ import annotations

import functools
import math
import re
from typing import List, Optional

from .tools import cleanup_out_data, js_to_fixed, to_fixed

_transform_types = {"matrix", "rotate", "scale", "skewX", "skewY", "translate"}

_reg_transform_split = re.compile(
    r"\s*(matrix|translate|scale|rotate|skewX|skewY)\s*\(\s*(.+?)\s*\)[\s,]*"
)
_reg_numeric_values = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def transform2js(transform_string: str) -> List[dict]:
    transforms: List[dict] = []
    current = None
    for item in _reg_transform_split.split(transform_string):
        if not item:
            continue
        if item in _transform_types:
            current = {"name": item, "data": []}
            transforms.append(current)
        else:
            for m in _reg_numeric_values.finditer(item):
                num = float(m.group(0))
                if current is not None:
                    current["data"].append(num)
    if current is None or len(current["data"]) == 0:
        return []
    return transforms


def transforms_multiply(transforms: List[dict]) -> dict:
    matrix_data = [
        t["data"] if t["name"] == "matrix" else transform_to_matrix(t) for t in transforms
    ]
    if len(matrix_data) > 0:
        data = functools.reduce(multiply_transform_matrices, matrix_data)
    else:
        data = []
    return {"name": "matrix", "data": data}


def _rad(deg):
    return (deg * math.pi) / 180


def _deg(rad):
    return (rad * 180) / math.pi


def _cos(deg):
    return math.cos(_rad(deg))


def _sin(deg):
    return math.sin(_rad(deg))


def _tan(deg):
    return math.tan(_rad(deg))


def _decompose_qrab(matrix):
    a, b, c, d, e, f = matrix["data"][:6]
    delta = a * d - b * c
    if delta == 0:
        return None
    r = math.hypot(a, b)
    if r == 0:
        return None
    decomposition = []
    cos_rot = a / r
    if e or f:
        decomposition.append({"name": "translate", "data": [e, f]})
    if cos_rot != 1:
        rot = math.acos(max(-1.0, min(1.0, cos_rot)))
        decomposition.append({"name": "rotate", "data": [_deg(-rot if b < 0 else rot), 0, 0]})
    sx = r
    sy = delta / sx
    if sx != 1 or sy != 1:
        decomposition.append({"name": "scale", "data": [sx, sy]})
    ac_plus_bd = a * c + b * d
    if ac_plus_bd:
        decomposition.append({"name": "skewX", "data": [_deg(math.atan(ac_plus_bd / (a * a + b * b)))]})
    return decomposition


def _decompose_qrcd(matrix):
    a, b, c, d, e, f = matrix["data"][:6]
    delta = a * d - b * c
    if delta == 0:
        return None
    s = math.hypot(c, d)
    if s == 0:
        return None
    decomposition = []
    if e or f:
        decomposition.append({"name": "translate", "data": [e, f]})
    rot = math.pi / 2 - (-1 if d < 0 else 1) * math.acos(max(-1.0, min(1.0, -c / s)))
    decomposition.append({"name": "rotate", "data": [_deg(rot), 0, 0]})
    sx = delta / s
    sy = s
    if sx != 1 or sy != 1:
        decomposition.append({"name": "scale", "data": [sx, sy]})
    ac_plus_bd = a * c + b * d
    if ac_plus_bd:
        decomposition.append({"name": "skewY", "data": [_deg(math.atan(ac_plus_bd / (c * c + d * d)))]})
    return decomposition


def _get_decompositions(matrix):
    result = []
    qrab = _decompose_qrab(matrix)
    qrcd = _decompose_qrcd(matrix)
    if qrab:
        result.append(qrab)
    if qrcd:
        result.append(qrcd)
    return result


def _merge_translate_and_rotate(tx, ty, a):
    rot = _rad(a)
    d = 1 - math.cos(rot)
    e = math.sin(rot)
    cy = (d * ty + e * tx) / (d * d + e * e)
    cx = (tx - e * cy) / d
    return {"name": "rotate", "data": [a, cx, cy]}


def _is_identity_transform(t):
    name = t["name"]
    data = t["data"]
    if name in ("rotate", "skewX", "skewY"):
        return data[0] == 0
    if name == "scale":
        return data[0] == 1 and data[1] == 1
    if name == "translate":
        return data[0] == 0 and data[1] == 0
    return False


def _create_scale_transform(data):
    scale_data = data[: 1 if (len(data) > 1 and data[0] == data[1]) or len(data) == 1 else 2]
    return {"name": "scale", "data": scale_data}


def _optimize(rounded_transforms, raw_transforms):
    optimized = []
    index = 0
    while index < len(rounded_transforms):
        rounded = rounded_transforms[index]
        if _is_identity_transform(rounded):
            index += 1
            continue
        data = rounded["data"]
        name = rounded["name"]
        if name == "rotate":
            if data[0] == 180 or data[0] == -180:
                nxt = rounded_transforms[index + 1] if index + 1 < len(rounded_transforms) else None
                if nxt and nxt["name"] == "scale":
                    optimized.append(_create_scale_transform([-v for v in nxt["data"]]))
                    index += 1
                else:
                    optimized.append({"name": "scale", "data": [-1]})
                index += 1
                continue
            keep = 3 if (len(data) > 1 and (data[1] or (len(data) > 2 and data[2]))) else 1
            optimized.append({"name": "rotate", "data": data[:keep]})
        elif name == "scale":
            optimized.append(_create_scale_transform(data))
        elif name in ("skewX", "skewY"):
            optimized.append({"name": name, "data": [data[0]]})
        elif name == "translate":
            nxt = rounded_transforms[index + 1] if index + 1 < len(rounded_transforms) else None
            if (
                nxt
                and nxt["name"] == "rotate"
                and nxt["data"][0] != 180
                and nxt["data"][0] != -180
                and nxt["data"][0] != 0
                and nxt["data"][1] == 0
                and nxt["data"][2] == 0
            ):
                raw = raw_transforms[index]["data"]
                optimized.append(
                    _merge_translate_and_rotate(raw[0], raw[1], raw_transforms[index + 1]["data"][0])
                )
                index += 2
                continue
            optimized.append({"name": "translate", "data": data[: 2 if (len(data) > 1 and data[1]) else 1]})
        index += 1
    return optimized if optimized else [{"name": "scale", "data": [1]}]


def matrix_to_transform(orig_matrix, params):
    decomposed = _get_decompositions(orig_matrix)
    shortest = None
    shortest_len = float("inf")
    for decomposition in decomposed:
        rounded = [
            round_transform({"name": t["name"], "data": list(t["data"])}, params)
            for t in decomposition
        ]
        optimized = _optimize(rounded, decomposition)
        # js2transform rounds the data in place; run it on `optimized` itself so
        # the chosen result keeps those rounded values (matches upstream).
        length = len(js2transform(optimized, params))
        if length < shortest_len:
            shortest = optimized
            shortest_len = length
    return shortest if shortest is not None else [orig_matrix]


def transform_to_matrix(transform):
    if transform["name"] == "matrix":
        return transform["data"]
    name = transform["name"]
    data = transform["data"]
    if name == "translate":
        return [1, 0, 0, 1, data[0], data[1] if len(data) > 1 else 0]
    if name == "scale":
        return [data[0], 0, 0, data[1] if len(data) > 1 else data[0], 0, 0]
    if name == "rotate":
        cos = _cos(data[0])
        sin = _sin(data[0])
        cx = data[1] if len(data) > 1 else 0
        cy = data[2] if len(data) > 2 else 0
        return [cos, sin, -sin, cos, (1 - cos) * cx + sin * cy, (1 - cos) * cy - sin * cx]
    if name == "skewX":
        return [1, 0, _tan(data[0]), 1, 0, 0]
    if name == "skewY":
        return [1, _tan(data[0]), 0, 1, 0, 0]
    raise ValueError(f"Unknown transform {name}")


def transform_arc(cursor, arc, transform):
    x = arc[5] - cursor[0]
    y = arc[6] - cursor[1]
    a = arc[0]
    b = arc[1]
    rot = (arc[2] * math.pi) / 180
    cos = math.cos(rot)
    sin = math.sin(rot)
    if a > 0 and b > 0:
        h = (x * cos + y * sin) ** 2 / (4 * a * a) + (y * cos - x * sin) ** 2 / (4 * b * b)
        if h > 1:
            h = math.sqrt(h)
            a *= h
            b *= h
    ellipse = [a * cos, a * sin, -b * sin, b * cos, 0, 0]
    m = multiply_transform_matrices(transform, ellipse)
    last_col = m[2] * m[2] + m[3] * m[3]
    square_sum = m[0] * m[0] + m[1] * m[1] + last_col
    root = math.hypot(m[0] - m[3], m[1] + m[2]) * math.hypot(m[0] + m[3], m[1] - m[2])
    if not root:
        arc[0] = arc[1] = math.sqrt(square_sum / 2)
        arc[2] = 0
    else:
        major_sqr = (square_sum + root) / 2
        minor_sqr = (square_sum - root) / 2
        major = abs(major_sqr - last_col) > 1e-6
        sub = (major_sqr if major else minor_sqr) - last_col
        rows_sum = m[0] * m[2] + m[1] * m[3]
        term1 = m[0] * sub + m[2] * rows_sum
        term2 = m[1] * sub + m[3] * rows_sum
        arc[0] = math.sqrt(major_sqr)
        arc[1] = math.sqrt(minor_sqr)
        cond = (term2 < 0) if major else (term1 > 0)
        val = (term1 if major else term2) / math.hypot(term1, term2)
        val = max(-1.0, min(1.0, val))
        arc[2] = ((-1 if cond else 1) * math.acos(val) * 180) / math.pi
    if (transform[0] < 0) != (transform[3] < 0):
        arc[4] = 1 - arc[4]
    return arc


def multiply_transform_matrices(a, b):
    return [
        a[0] * b[0] + a[2] * b[1],
        a[1] * b[0] + a[3] * b[1],
        a[0] * b[2] + a[2] * b[3],
        a[1] * b[2] + a[3] * b[3],
        a[0] * b[4] + a[2] * b[5] + a[4],
        a[1] * b[4] + a[3] * b[5] + a[5],
    ]


def round_transform(transform, params):
    name = transform["name"]
    data = transform["data"]
    if name == "translate":
        transform["data"] = _float_round(data, params)
    elif name == "rotate":
        transform["data"] = _deg_round(data[:1], params) + _float_round(data[1:], params)
    elif name in ("skewX", "skewY"):
        transform["data"] = _deg_round(data, params)
    elif name == "scale":
        transform["data"] = _transform_round(data, params)
    elif name == "matrix":
        transform["data"] = _transform_round(data[:4], params) + _float_round(data[4:], params)
    return transform


def _deg_round(data, params):
    deg_precision = params.get("degPrecision")
    if deg_precision is not None and deg_precision >= 1 and params["floatPrecision"] < 20:
        return _smart_round(deg_precision, data)
    return _round(data)


def _float_round(data, params):
    if params["floatPrecision"] >= 1 and params["floatPrecision"] < 20:
        return _smart_round(params["floatPrecision"], data)
    return _round(data)


def _transform_round(data, params):
    if params["transformPrecision"] >= 1 and params["floatPrecision"] < 20:
        return _smart_round(params["transformPrecision"], data)
    return _round(data)


def _round(data):
    from .tools import _js_round

    return [_js_round(v) for v in data]


def _smart_round(precision, data):
    tolerance = js_to_fixed(math.pow(0.1, precision), precision)
    data = list(data)
    for i in range(len(data)):
        if to_fixed(data[i], precision) != data[i]:
            rounded = js_to_fixed(data[i], precision - 1)
            if js_to_fixed(abs(rounded - data[i]), precision + 1) >= tolerance:
                data[i] = js_to_fixed(data[i], precision)
            else:
                data[i] = rounded
    return data


def js2transform(transform_js, params):
    parts = []
    for transform in transform_js:
        round_transform(transform, params)
        parts.append(f"{transform['name']}({cleanup_out_data(transform['data'], params)})")
    return "".join(parts)
