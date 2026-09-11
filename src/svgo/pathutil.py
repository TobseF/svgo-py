"""Path helpers for convertPathData/mergePaths. Port of ``plugins/_path.js``."""

from __future__ import annotations

import math
from typing import List, Optional

from .path import parse_path_data, stringify_path_data
from .tools import js_to_fixed

# Shared control point state (mirrors the module-level `prevCtrlPoint` in JS).
_prev_ctrl_point = [0.0, 0.0]


def path2js(path):
    cached = getattr(path, "pathJS", None)
    if cached is not None:
        return cached
    path_data = []
    for item in parse_path_data(path.attributes["d"]):
        path_data.append({"command": item["command"], "args": item["args"]})
    if path_data and path_data[0]["command"] == "m":
        path_data[0]["command"] = "M"
    path.pathJS = path_data
    return path_data


def _convert_relative_to_absolute(data):
    new_data = []
    start = [0.0, 0.0]
    cursor = [0.0, 0.0]
    for item in data:
        command = item["command"]
        args = list(item["args"])
        if command == "m":
            args[0] += cursor[0]
            args[1] += cursor[1]
            command = "M"
        if command == "M":
            cursor[0] = args[0]
            cursor[1] = args[1]
            start[0] = cursor[0]
            start[1] = cursor[1]
        if command == "h":
            args[0] += cursor[0]
            command = "H"
        if command == "H":
            cursor[0] = args[0]
        if command == "v":
            args[0] += cursor[1]
            command = "V"
        if command == "V":
            cursor[1] = args[0]
        if command == "l":
            args[0] += cursor[0]
            args[1] += cursor[1]
            command = "L"
        if command == "L":
            cursor[0] = args[0]
            cursor[1] = args[1]
        if command == "c":
            args[0] += cursor[0]; args[1] += cursor[1]
            args[2] += cursor[0]; args[3] += cursor[1]
            args[4] += cursor[0]; args[5] += cursor[1]
            command = "C"
        if command == "C":
            cursor[0] = args[4]; cursor[1] = args[5]
        if command == "s":
            args[0] += cursor[0]; args[1] += cursor[1]
            args[2] += cursor[0]; args[3] += cursor[1]
            command = "S"
        if command == "S":
            cursor[0] = args[2]; cursor[1] = args[3]
        if command == "q":
            args[0] += cursor[0]; args[1] += cursor[1]
            args[2] += cursor[0]; args[3] += cursor[1]
            command = "Q"
        if command == "Q":
            cursor[0] = args[2]; cursor[1] = args[3]
        if command == "t":
            args[0] += cursor[0]; args[1] += cursor[1]
            command = "T"
        if command == "T":
            cursor[0] = args[0]; cursor[1] = args[1]
        if command == "a":
            args[5] += cursor[0]; args[6] += cursor[1]
            command = "A"
        if command == "A":
            cursor[0] = args[5]; cursor[1] = args[6]
        if command == "z" or command == "Z":
            cursor[0] = start[0]; cursor[1] = start[1]
            command = "z"
        new_data.append({"command": command, "args": args})
    return new_data


def js2path(path, data, params):
    path.pathJS = data
    path_data = []
    for item in data:
        if path_data and item["command"] in ("M", "m"):
            last = path_data[-1]
            if last["command"] in ("M", "m"):
                path_data.pop()
        path_data.append({"command": item["command"], "args": item["args"]})
    path.attributes["d"] = stringify_path_data(
        path_data,
        precision=params.get("floatPrecision"),
        disableSpaceAfterFlags=params.get("noSpaceAfterFlags", False),
    )


def _set(dest, source):
    dest[0] = source[len(source) - 2]
    dest[1] = source[len(source) - 1]
    return dest


def _minus(v):
    return [-v[0], -v[1]]


def _sub(v1, v2):
    return [v1[0] - v2[0], v1[1] - v2[1]]


def _dot(v1, v2):
    return v1[0] * v2[0] + v1[1] * v2[1]


def _orth(v, from_):
    o = [-v[1], v[0]]
    return _minus(o) if _dot(o, _minus(from_)) < 0 else o


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def intersects(path1, path2):
    points1 = _gather_points(_convert_relative_to_absolute(path1))
    points2 = _gather_points(_convert_relative_to_absolute(path2))

    def aabb_all():
        for set1 in points1["list"]:
            for set2 in points2["list"]:
                if not (
                    set1["list"][set1["maxX"]][0] <= set2["list"][set2["minX"]][0]
                    or set2["list"][set2["maxX"]][0] <= set1["list"][set1["minX"]][0]
                    or set1["list"][set1["maxY"]][1] <= set2["list"][set2["minY"]][1]
                    or set2["list"][set2["maxY"]][1] <= set1["list"][set1["minY"]][1]
                ):
                    return False
        return True

    if (
        points1["maxX"] <= points2["minX"]
        or points2["maxX"] <= points1["minX"]
        or points1["maxY"] <= points2["minY"]
        or points2["maxY"] <= points1["minY"]
        or aabb_all()
    ):
        return False

    hull_nest1 = [_convex_hull(p) for p in points1["list"]]
    hull_nest2 = [_convex_hull(p) for p in points2["list"]]

    def support_point(polygon, direction):
        if direction[1] >= 0:
            index = polygon["maxY"] if direction[0] < 0 else polygon["maxX"]
        else:
            index = polygon["minX"] if direction[0] < 0 else polygon["minY"]
        max_ = -math.inf
        while True:
            value = _dot(polygon["list"][index], direction)
            if value > max_:
                max_ = value
                index = (index + 1) % len(polygon["list"])
            else:
                break
        return polygon["list"][(index or len(polygon["list"])) - 1]

    def get_support(a, b, direction):
        return _sub(support_point(a, direction), support_point(b, _minus(direction)))

    for hull1 in hull_nest1:
        if len(hull1["list"]) < 3:
            continue
        for hull2 in hull_nest2:
            if len(hull2["list"]) < 3:
                continue
            simplex = [get_support(hull1, hull2, [1, 0])]
            direction = _minus(simplex[0])
            iterations = 10000
            while True:
                iterations -= 1
                if iterations == 0:
                    return True
                simplex.append(get_support(hull1, hull2, direction))
                if _dot(direction, simplex[-1]) <= 0:
                    break
                if _process_simplex(simplex, direction):
                    return True
    return False


def _process_simplex(simplex, direction):
    if len(simplex) == 2:
        a = simplex[1]
        b = simplex[0]
        AO = _minus(simplex[1])
        AB = _sub(b, a)
        if _dot(AO, AB) > 0:
            _set(direction, _orth(AB, a))
        else:
            _set(direction, AO)
            simplex.pop(0)
    else:
        a = simplex[2]
        b = simplex[1]
        c = simplex[0]
        AB = _sub(b, a)
        AC = _sub(c, a)
        AO = _minus(a)
        ACB = _orth(AB, AC)
        ABC = _orth(AC, AB)
        if _dot(ACB, AO) > 0:
            if _dot(AB, AO) > 0:
                _set(direction, ACB)
                simplex.pop(0)
            else:
                _set(direction, AO)
                del simplex[0:2]
        elif _dot(ABC, AO) > 0:
            if _dot(AC, AO) > 0:
                _set(direction, ABC)
                del simplex[1:2]
            else:
                _set(direction, AO)
                del simplex[0:2]
        else:
            return True
    return False


def _gather_points(path_data):
    points = {"list": [], "minX": 0, "minY": 0, "maxX": 0, "maxY": 0}

    def add_point(path, point):
        if not path["list"] or point[1] > path["list"][path["maxY"]][1]:
            path["maxY"] = len(path["list"])
            points["maxY"] = max(point[1], points["maxY"]) if points["list"] else point[1]
        if not path["list"] or point[0] > path["list"][path["maxX"]][0]:
            path["maxX"] = len(path["list"])
            points["maxX"] = max(point[0], points["maxX"]) if points["list"] else point[0]
        if not path["list"] or point[1] < path["list"][path["minY"]][1]:
            path["minY"] = len(path["list"])
            points["minY"] = min(point[1], points["minY"]) if points["list"] else point[1]
        if not path["list"] or point[0] < path["list"][path["minX"]][0]:
            path["minX"] = len(path["list"])
            points["minX"] = min(point[0], points["minX"]) if points["list"] else point[0]
        path["list"].append(point)

    global _prev_ctrl_point

    for i in range(len(path_data)):
        path_data_item = path_data[i]
        if len(points["list"]) == 0:
            sub_path = {"list": [], "minX": 0, "minY": 0, "maxX": 0, "maxY": 0}
        else:
            sub_path = points["list"][-1]
        prev = None if i == 0 else path_data[i - 1]
        base_point = None if len(sub_path["list"]) == 0 else sub_path["list"][-1]
        data = path_data_item["args"]
        ctrl_point = base_point

        def to_absolute(n, idx):
            return n + (0 if base_point is None else base_point[idx % 2])

        cmd = path_data_item["command"]
        if cmd == "M":
            sub_path = {"list": [], "minX": 0, "minY": 0, "maxX": 0, "maxY": 0}
            points["list"].append(sub_path)
        elif cmd == "H":
            if base_point is not None:
                add_point(sub_path, [data[0], base_point[1]])
        elif cmd == "V":
            if base_point is not None:
                add_point(sub_path, [base_point[0], data[0]])
        elif cmd == "Q":
            add_point(sub_path, list(data[0:2]))
            _prev_ctrl_point = [data[2] - data[0], data[3] - data[1]]
        elif cmd == "T":
            if base_point is not None and prev is not None and prev["command"] in ("Q", "T"):
                ctrl_point = [base_point[0] + _prev_ctrl_point[0], base_point[1] + _prev_ctrl_point[1]]
                add_point(sub_path, ctrl_point)
                _prev_ctrl_point = [data[0] - ctrl_point[0], data[1] - ctrl_point[1]]
        elif cmd == "C":
            if base_point is not None:
                add_point(sub_path, [0.5 * (base_point[0] + data[0]), 0.5 * (base_point[1] + data[1])])
            add_point(sub_path, [0.5 * (data[0] + data[2]), 0.5 * (data[1] + data[3])])
            add_point(sub_path, [0.5 * (data[2] + data[4]), 0.5 * (data[3] + data[5])])
            _prev_ctrl_point = [data[4] - data[2], data[5] - data[3]]
        elif cmd == "S":
            if base_point is not None and prev is not None and prev["command"] in ("C", "S"):
                add_point(sub_path, [base_point[0] + 0.5 * _prev_ctrl_point[0], base_point[1] + 0.5 * _prev_ctrl_point[1]])
                ctrl_point = [base_point[0] + _prev_ctrl_point[0], base_point[1] + _prev_ctrl_point[1]]
            if ctrl_point is not None:
                add_point(sub_path, [0.5 * (ctrl_point[0] + data[0]), 0.5 * (ctrl_point[1] + data[1])])
            add_point(sub_path, [0.5 * (data[0] + data[2]), 0.5 * (data[1] + data[3])])
            _prev_ctrl_point = [data[2] - data[0], data[3] - data[1]]
        elif cmd == "A":
            if base_point is not None:
                curves = _a2c(*(list(base_point) + list(data)))
                while True:
                    chunk = curves[0:6]
                    del curves[0:6]
                    c_data = [to_absolute(chunk[j], j) for j in range(len(chunk))]
                    if len(c_data) == 0:
                        break
                    if base_point is not None:
                        add_point(sub_path, [0.5 * (base_point[0] + c_data[0]), 0.5 * (base_point[1] + c_data[1])])
                    add_point(sub_path, [0.5 * (c_data[0] + c_data[2]), 0.5 * (c_data[1] + c_data[3])])
                    add_point(sub_path, [0.5 * (c_data[2] + c_data[4]), 0.5 * (c_data[3] + c_data[5])])
                    if len(curves):
                        base_point = c_data[-2:]
                        add_point(sub_path, base_point)

        if len(data) >= 2:
            add_point(sub_path, list(data[-2:]))

    return points


def _convex_hull(points):
    points["list"].sort(key=_cmp_to_key_hull())

    lower = []
    min_y = 0
    bottom = 0
    for i in range(len(points["list"])):
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], points["list"][i]) <= 0:
            lower.pop()
        if points["list"][i][1] < points["list"][min_y][1]:
            min_y = i
            bottom = len(lower)
        lower.append(points["list"][i])

    upper = []
    max_y = len(points["list"]) - 1
    top = 0
    for i in range(len(points["list"]) - 1, -1, -1):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], points["list"][i]) <= 0:
            upper.pop()
        if points["list"][i][1] > points["list"][max_y][1]:
            max_y = i
            top = len(upper)
        upper.append(points["list"][i])

    upper.pop()
    lower.pop()
    hull_list = lower + upper
    return {
        "list": hull_list,
        "minX": 0,
        "maxX": len(lower),
        "minY": bottom,
        "maxY": (len(lower) + top) % len(hull_list) if hull_list else 0,
    }


def _cmp_to_key_hull():
    import functools

    def cmp(a, b):
        if a[0] == b[0]:
            d = a[1] - b[1]
        else:
            d = a[0] - b[0]
        return -1 if d < 0 else (1 if d > 0 else 0)

    return functools.cmp_to_key(cmp)


def _a2c(x1, y1, rx, ry, angle, large_arc_flag, sweep_flag, x2, y2, recursive=None):
    _120 = (math.pi * 120) / 180
    rad = (math.pi / 180) * ((angle or 0))
    res = []

    def rotate_x(x, y, r):
        return x * math.cos(r) - y * math.sin(r)

    def rotate_y(x, y, r):
        return x * math.sin(r) + y * math.cos(r)

    if not recursive:
        x1 = rotate_x(x1, y1, -rad)
        y1 = rotate_y(x1, y1, -rad)
        x2 = rotate_x(x2, y2, -rad)
        y2 = rotate_y(x2, y2, -rad)
        x = (x1 - x2) / 2
        y = (y1 - y2) / 2
        h = (x * x) / (rx * rx) + (y * y) / (ry * ry)
        if h > 1:
            h = math.sqrt(h)
            rx = h * rx
            ry = h * ry
        rx2 = rx * rx
        ry2 = ry * ry
        k = (-1 if large_arc_flag == sweep_flag else 1) * math.sqrt(
            abs((rx2 * ry2 - rx2 * y * y - ry2 * x * x) / (rx2 * y * y + ry2 * x * x))
        )
        cx = (k * rx * y) / ry + (x1 + x2) / 2
        cy = (k * -ry * x) / rx + (y1 + y2) / 2
        f1 = math.asin(max(-1.0, min(1.0, js_to_fixed((y1 - cy) / ry, 9))))
        f2 = math.asin(max(-1.0, min(1.0, js_to_fixed((y2 - cy) / ry, 9))))
        f1 = math.pi - f1 if x1 < cx else f1
        f2 = math.pi - f2 if x2 < cx else f2
        if f1 < 0:
            f1 = math.pi * 2 + f1
        if f2 < 0:
            f2 = math.pi * 2 + f2
        if sweep_flag and f1 > f2:
            f1 = f1 - math.pi * 2
        if not sweep_flag and f2 > f1:
            f2 = f2 - math.pi * 2
    else:
        f1, f2, cx, cy = recursive[0], recursive[1], recursive[2], recursive[3]

    df = f2 - f1
    if abs(df) > _120:
        f2old = f2
        x2old = x2
        y2old = y2
        f2 = f1 + _120 * (1 if (sweep_flag and f2 > f1) else -1)
        x2 = cx + rx * math.cos(f2)
        y2 = cy + ry * math.sin(f2)
        res = _a2c(x2, y2, rx, ry, angle, 0, sweep_flag, x2old, y2old, [f2, f2old, cx, cy])

    df = f2 - f1
    c1 = math.cos(f1)
    s1 = math.sin(f1)
    c2 = math.cos(f2)
    s2 = math.sin(f2)
    t = math.tan(df / 4)
    hx = (4 / 3) * rx * t
    hy = (4 / 3) * ry * t
    m = [
        -hx * s1,
        hy * c1,
        x2 + hx * s2 - x1,
        y2 - hy * c2 - y1,
        x2 - x1,
        y2 - y1,
    ]
    if recursive:
        return m + res
    else:
        res = m + res
        newres = []
        for i in range(len(res)):
            if i % 2:
                newres.append(rotate_y(res[i - 1], res[i], rad))
            else:
                newres.append(rotate_x(res[i], res[i + 1], rad))
        return newres
