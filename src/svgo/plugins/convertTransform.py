import re

from ..tools import js_number_to_string
from ..transforms import (
    js2transform,
    matrix_to_transform,
    round_transform,
    transform2js,
    transforms_multiply,
)

name = "convertTransform"
description = "collapses multiple transformations and optimizes it"


def fn(root, params, info):
    new_params = {
        "convertToShorts": params.get("convertToShorts", True),
        "degPrecision": params.get("degPrecision"),
        "floatPrecision": params.get("floatPrecision", 3),
        "transformPrecision": params.get("transformPrecision", 5),
        "matrixToTransform": params.get("matrixToTransform", True),
        "shortTranslate": params.get("shortTranslate", True),
        "shortScale": params.get("shortScale", True),
        "shortRotate": params.get("shortRotate", True),
        "removeUseless": params.get("removeUseless", True),
        "collapseIntoOne": params.get("collapseIntoOne", True),
        "leadingZero": params.get("leadingZero", True),
        "negativeExtraSpace": params.get("negativeExtraSpace", False),
    }

    def enter(node):
        for attr in ("transform", "gradientTransform", "patternTransform"):
            if node.attributes.get(attr) is not None:
                _convert_transform(node, attr, new_params)

    return {"element": {"enter": lambda node, parent_node: enter(node)}}


def _convert_transform(item, attr_name, params):
    data = transform2js(item.attributes[attr_name])
    params = _define_precision(data, params)

    if params["collapseIntoOne"] and len(data) > 1:
        data = [transforms_multiply(data)]

    if params["convertToShorts"]:
        data = _convert_to_shorts(data, params)
    else:
        for t in data:
            round_transform(t, params)

    if params["removeUseless"]:
        data = _remove_useless(data)

    if len(data):
        item.attributes[attr_name] = js2transform(data, params)
    else:
        del item.attributes[attr_name]


def _float_digits(n):
    s = js_number_to_string(n)
    if "." in s:
        return len(s) - s.index(".") - 1
    return 0


def _digit_count(n):
    s = js_number_to_string(n)
    return len(re.sub(r"\D+", "", s))


def _define_precision(data, params):
    new_params = dict(params)
    matrix_data = []
    for item in data:
        if item["name"] == "matrix":
            matrix_data.extend(item["data"][:4])
    number_of_digits = new_params["transformPrecision"]
    if matrix_data:
        float_digits_max = max((_float_digits(n) for n in matrix_data), default=0)
        new_params["transformPrecision"] = min(
            new_params["transformPrecision"],
            float_digits_max or new_params["transformPrecision"],
        )
        number_of_digits = max(_digit_count(n) for n in matrix_data)
    if new_params.get("degPrecision") is None:
        new_params["degPrecision"] = max(
            0, min(new_params["floatPrecision"], number_of_digits - 2)
        )
    return new_params


def _convert_to_shorts(transforms, params):
    i = 0
    while i < len(transforms):
        transform = transforms[i]

        if params["matrixToTransform"] and transform["name"] == "matrix":
            decomposed = matrix_to_transform(transform, params)
            if len(js2transform(decomposed, params)) <= len(js2transform([transform], params)):
                transforms[i:i + 1] = decomposed
            transform = transforms[i]

        round_transform(transform, params)

        if (
            params["shortTranslate"]
            and transform["name"] == "translate"
            and len(transform["data"]) == 2
            and not transform["data"][1]
        ):
            transform["data"].pop()

        if (
            params["shortScale"]
            and transform["name"] == "scale"
            and len(transform["data"]) == 2
            and transform["data"][0] == transform["data"][1]
        ):
            transform["data"].pop()

        if (
            params["shortRotate"]
            and i - 2 >= 0
            and transforms[i - 2]["name"] == "translate"
            and transforms[i - 1]["name"] == "rotate"
            and transforms[i]["name"] == "translate"
            and transforms[i - 2]["data"][0] == -transforms[i]["data"][0]
            and transforms[i - 2]["data"][1] == -transforms[i]["data"][1]
        ):
            merged = {
                "name": "rotate",
                "data": [
                    transforms[i - 1]["data"][0],
                    transforms[i - 2]["data"][0],
                    transforms[i - 2]["data"][1],
                ],
            }
            transforms[i - 2:i + 1] = [merged]
            i -= 2
        i += 1

    return transforms


def _remove_useless(transforms):
    result = []
    for transform in transforms:
        name_ = transform["name"]
        data = transform["data"]
        useless = (
            (
                name_ in ("translate", "rotate", "skewX", "skewY")
                and (len(data) == 1 or name_ == "rotate")
                and not data[0]
            )
            or (name_ == "translate" and not data[0] and (len(data) < 2 or not data[1]))
            or (
                name_ == "scale"
                and data[0] == 1
                and (len(data) < 2 or data[1] == 1)
            )
            or (
                name_ == "matrix"
                and data[0] == 1
                and data[3] == 1
                and not (data[1] or data[2] or data[4] or data[5])
            )
        )
        if not useless:
            result.append(transform)
    return result
