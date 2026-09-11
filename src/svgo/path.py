"""SVG path data parsing/stringifying. Port of ``lib/path.js``.

A path-data item is a dict ``{"command": str, "args": [float, ...]}``.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .tools import remove_leading_zero, to_fixed

_JS_FLOAT_PREFIX = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


def _js_parse_float(value: str) -> Optional[float]:
    """Replicate JavaScript ``Number.parseFloat``: parse the longest valid
    numeric prefix, ignoring a trailing incomplete exponent (e.g. ``5e+`` -> 5).
    """
    match = _JS_FLOAT_PREFIX.match(value)
    if match is None:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None

_ARGS_COUNT = {
    "M": 2, "m": 2, "Z": 0, "z": 0, "L": 2, "l": 2, "H": 1, "h": 1,
    "V": 1, "v": 1, "C": 6, "c": 6, "S": 4, "s": 4, "Q": 4, "q": 4,
    "T": 2, "t": 2, "A": 7, "a": 7,
}


def _is_command(c: str) -> bool:
    return c in _ARGS_COUNT


def _is_whitespace(c: str) -> bool:
    return c in (" ", "\t", "\r", "\n")


def _is_digit(c: str) -> bool:
    return len(c) == 1 and "0" <= c <= "9"


def _read_number(string: str, cursor: int) -> Tuple[int, Optional[float]]:
    i = cursor
    value = ""
    state = "none"
    n = len(string)
    while i < n:
        c = string[i]
        if c == "+" or c == "-":
            if state == "none":
                state = "sign"
                value += c
                i += 1
                continue
            if state == "e":
                state = "exponent_sign"
                value += c
                i += 1
                continue
        if _is_digit(c):
            if state in ("none", "sign", "whole"):
                state = "whole"
                value += c
                i += 1
                continue
            if state in ("decimal_point", "decimal"):
                state = "decimal"
                value += c
                i += 1
                continue
            if state in ("e", "exponent_sign", "exponent"):
                state = "exponent"
                value += c
                i += 1
                continue
        if c == ".":
            if state in ("none", "sign", "whole"):
                state = "decimal_point"
                value += c
                i += 1
                continue
        if c == "E" or c == "e":
            if state in ("whole", "decimal_point", "decimal"):
                state = "e"
                value += c
                i += 1
                continue
        break
    number = _js_parse_float(value)
    if number is None or number != number:  # None or NaN
        return cursor, None
    return i - 1, number


def parse_path_data(string: str) -> List[dict]:
    path_data: List[dict] = []
    command = None
    args: List[float] = []
    args_count = 0
    can_have_comma = False
    had_comma = False
    i = 0
    n = len(string)
    while i < n:
        c = string[i]
        if _is_whitespace(c):
            i += 1
            continue
        if can_have_comma and c == ",":
            if had_comma:
                break
            had_comma = True
            i += 1
            continue
        if _is_command(c):
            if had_comma:
                return path_data
            if command is None:
                if c != "M" and c != "m":
                    return path_data
            elif len(args) != 0:
                return path_data
            command = c
            args = []
            args_count = _ARGS_COUNT[command]
            can_have_comma = False
            if args_count == 0:
                path_data.append({"command": command, "args": args})
            i += 1
            continue
        if command is None:
            return path_data
        new_cursor = i
        number = None
        if command == "A" or command == "a":
            position = len(args)
            if position in (0, 1, 2, 5, 6):
                new_cursor, number = _read_number(string, i)
            if position in (3, 4):
                if c == "0":
                    number = 0
                if c == "1":
                    number = 1
        else:
            new_cursor, number = _read_number(string, i)
        if number is None:
            return path_data
        args.append(number)
        can_have_comma = True
        had_comma = False
        i = new_cursor
        if len(args) == args_count:
            if command == "A" or command == "a":
                args[0] = abs(args[0])
                args[1] = abs(args[1])
            path_data.append({"command": command, "args": args})
            if command == "M":
                command = "L"
            if command == "m":
                command = "l"
            args = []
        i += 1
    return path_data


def _round_and_stringify(number: float, precision: Optional[int]):
    if precision is not None:
        number = to_fixed(number, precision)
    return remove_leading_zero(number), number


def _is_integer(x) -> bool:
    return float(x).is_integer()


def _stringify_args(command, args, precision, disable_space_after_flags) -> str:
    result = ""
    previous = None
    for i in range(len(args)):
        rounded_str, rounded = _round_and_stringify(args[i], precision)
        if (
            disable_space_after_flags
            and command in ("A", "a")
            and (i % 7 == 4 or i % 7 == 5)
        ):
            result += rounded_str
        elif i == 0 or rounded < 0:
            result += rounded_str
        elif not _is_integer(previous) and not _is_digit(rounded_str[0]):
            result += rounded_str
        else:
            result += " " + rounded_str
        previous = rounded
    return result


def stringify_path_data(pathData, precision=None, disableSpaceAfterFlags=False) -> str:
    if len(pathData) == 1:
        item = pathData[0]
        return item["command"] + _stringify_args(
            item["command"], item["args"], precision, disableSpaceAfterFlags
        )

    result = ""
    prev = {"command": pathData[0]["command"], "args": list(pathData[0]["args"])}

    if pathData[1]["command"] == "L":
        prev["command"] = "M"
    elif pathData[1]["command"] == "l":
        prev["command"] = "m"

    for i in range(1, len(pathData)):
        command = pathData[i]["command"]
        args = pathData[i]["args"]
        if (
            (prev["command"] == command and prev["command"] != "M" and prev["command"] != "m")
            or (prev["command"] == "M" and command == "L")
            or (prev["command"] == "m" and command == "l")
        ):
            prev["args"] = list(prev["args"]) + list(args)
            if i == len(pathData) - 1:
                result += prev["command"] + _stringify_args(
                    prev["command"], prev["args"], precision, disableSpaceAfterFlags
                )
        else:
            result += prev["command"] + _stringify_args(
                prev["command"], prev["args"], precision, disableSpaceAfterFlags
            )
            if i == len(pathData) - 1:
                result += command + _stringify_args(
                    command, args, precision, disableSpaceAfterFlags
                )
            else:
                prev = {"command": command, "args": args}

    return result
