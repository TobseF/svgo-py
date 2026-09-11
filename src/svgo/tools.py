"""Assorted helpers. Port of ``lib/svgo/tools.js``."""

from __future__ import annotations

import base64
import re
import urllib.parse
from typing import List, Optional

from .collections import attrsGroups, referencesProps

# JS source: /\burl\((["'])?#(.+?)\1\)/g -- Python cannot backreference an
# optional group that did not participate, so the three quoting variants are
# spelled out explicitly. The captured id is whichever group matched.
_reg_references_url = re.compile(
    r"\burl\((?:\"#(.+?)\"|'#(.+?)'|#(.+?))\)"
)
_reg_references_href = re.compile(r"^#(.+?)$")


def _url_ref_id(match: "re.Match[str]") -> str:
    return match.group(1) or match.group(2) or match.group(3)
_reg_references_begin = re.compile(r"(\w+)\.[a-zA-Z]")


def encode_svg_datauri(s: str, type_: Optional[str] = None) -> str:
    prefix = "data:image/svg+xml"
    if not type_ or type_ == "base64":
        prefix += ";base64,"
        return prefix + base64.b64encode(s.encode("utf-8")).decode("ascii")
    if type_ == "enc":
        return prefix + "," + urllib.parse.quote(s, safe="!~*'()")
    if type_ == "unenc":
        return prefix + "," + s
    return s


def decode_svg_datauri(s: str) -> str:
    regexp = re.compile(r"data:image/svg\+xml(;charset=[^;,]*)?(;base64)?,(.*)", re.DOTALL)
    match = regexp.match(s)
    if not match:
        return s
    data = match.group(3)
    if match.group(2):
        return base64.b64decode(data).decode("utf-8")
    if data[:1] == "%":
        return urllib.parse.unquote(data)
    if data[:1] == "<":
        return data
    return s


def remove_leading_zero(value: float) -> str:
    """0.5 -> .5 ; -0.5 -> -.5"""
    str_value = js_number_to_string(value)
    if 0 < value < 1 and str_value.startswith("0"):
        return str_value[1:]
    if -1 < value < 0 and str_value[1:2] == "0":
        return str_value[0] + str_value[2:]
    return str_value


def _format_ecma(s: str, k: int, n: int) -> str:
    """ECMA-262 Number::toString formatting from shortest digits ``s`` (k
    digits) and decimal position ``n`` (value == s x 10**(n-k))."""
    if k <= n <= 21:
        return s + "0" * (n - k)
    if 0 < n <= 21:
        return s[:n] + "." + s[n:]
    if -6 < n <= 0:
        return "0." + "0" * (-n) + s
    # exponential form
    e = n - 1
    esign = "+" if e >= 0 else "-"
    mant = s if k == 1 else s[0] + "." + s[1:]
    return mant + "e" + esign + str(abs(e))


def js_number_to_string(value) -> str:
    """Format a number exactly the way JavaScript's ``Number.prototype.toString``
    does, including exponent thresholds (``< 1e-6`` / ``>= 1e21``) and exponent
    spelling (``1e-7`` not Python's ``1e-07``).
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if value != value:
            return "NaN"
        if value == float("inf"):
            return "Infinity"
        if value == float("-inf"):
            return "-Infinity"
    if value == 0:
        return "0"

    neg = value < 0
    r = repr(abs(value))

    if "e" in r or "E" in r:
        mant, _, exp_str = r.replace("E", "e").partition("e")
        exp = int(exp_str)
        if "." in mant:
            intp, frac = mant.split(".")
        else:
            intp, frac = mant, ""
        digits = intp + frac
        pointexp = exp - len(frac)
    else:
        if "." in r:
            intp, frac = r.split(".")
        else:
            intp, frac = r, ""
        digits = intp + frac
        pointexp = -len(frac)

    # strip insignificant leading zeros (do not change the integer value)
    digits = digits.lstrip("0") or "0"
    # strip trailing zeros, compensating the exponent
    stripped = digits.rstrip("0") or "0"
    pointexp += len(digits) - len(stripped)
    s = stripped
    k = len(s)
    n = pointexp + k

    result = _format_ecma(s, k, n)
    return "-" + result if neg else result


def cleanup_out_data(data: List[float], params, command: Optional[str] = None) -> str:
    """Convert a row of numbers to an optimized string view."""
    result = []
    prev = 0.0
    leading_zero = params.get("leadingZero", True)
    negative_extra_space = params.get("negativeExtraSpace", False)
    no_space_after_flags = params.get("noSpaceAfterFlags", False)

    for i, item in enumerate(data):
        delimiter = " "
        if i == 0:
            delimiter = ""

        if no_space_after_flags and command in ("A", "a"):
            pos = i % 7
            if pos == 4 or pos == 5:
                delimiter = ""

        item_str = remove_leading_zero(item) if leading_zero else js_number_to_string(item)

        if (
            negative_extra_space
            and delimiter != ""
            and (item < 0 or (item_str[:1] == "." and (prev % 1) != 0))
        ):
            delimiter = ""
        prev = item
        result.append(delimiter + item_str)
    return "".join(result)


_hasScriptsEventAttrs = (
    list(attrsGroups.get("animationEvent", set()))
    + list(attrsGroups.get("documentEvent", set()))
    + list(attrsGroups.get("documentElementEvent", set()))
    + list(attrsGroups.get("globalEvent", set()))
    + list(attrsGroups.get("graphicalEvent", set()))
)

_executable_data_media_types = {
    "application/xhtml+xml",
    "image/svg+xml",
    "text/html",
}


def is_executable_url(value: str) -> bool:
    normalized = re.sub(r"[\t\n\r]", "", value).lstrip().lower()
    if normalized.startswith("javascript:") or normalized.startswith("vbscript:"):
        return True
    if not normalized.startswith("data:"):
        return False
    rest = normalized[5:]
    m = re.search(r"[;,]", rest)
    if m is None:
        return False
    media_type = rest[: m.start()].strip()
    return media_type in _executable_data_media_types


def has_scripts(node) -> bool:
    if node.name == "script" and len(node.children) != 0:
        return True
    if node.name == "a":
        for attr_key, attr_value in node.attributes.items():
            if (attr_key == "href" or attr_key.endswith(":href")) and attr_value is not None and is_executable_url(attr_value):
                return True
    return any(node.attributes.get(attr) is not None for attr in _hasScriptsEventAttrs)


def includes_url_reference(body: str) -> bool:
    return re.search(_reg_references_url, body) is not None


def includes_css_var_reference(body: str) -> bool:
    return re.search(r"var\s*\(\s*--", body) is not None


def find_references(attribute: str, value: str) -> List[str]:
    results = []
    if attribute in referencesProps:
        for match in _reg_references_url.finditer(value):
            results.append(_url_ref_id(match))
    if attribute == "href" or attribute.endswith(":href"):
        match = _reg_references_href.match(value)
        if match is not None:
            results.append(match.group(1))
    if attribute == "begin":
        match = _reg_references_begin.search(value)
        if match is not None:
            results.append(match.group(1))
    return [urllib.parse.unquote(body) for body in results]


def js_number(value) -> float:
    """Replicate JavaScript ``Number(value)`` for the cases SVGO relies on.

    ``Number('')`` and ``Number(' ')`` are ``0``; surrounding whitespace is
    ignored; anything not fully numeric (e.g. ``'100%'``) is ``NaN``.
    """
    if value is None:
        return float("nan")
    if isinstance(value, (int, float)):
        return float(value)
    s = value.strip()
    if s == "":
        return 0.0
    try:
        return float(s)
    except ValueError:
        # hex / other JS forms are uncommon in SVG geometry; treat as NaN
        return float("nan")


def to_fixed(num: float, precision: int) -> float:
    pow_ = 10 ** precision
    return _js_round(num * pow_) / pow_


def js_to_fixed(x: float, precision: int) -> float:
    """Replicate ``Number(x.toFixed(precision))``.

    JavaScript's ``toFixed`` rounds the *exact* binary value of the double with
    ties going away from zero. Using ``Decimal(x)`` (the exact float, not its
    repr) with ``ROUND_HALF_UP`` reproduces this, including the well-known
    ``(1.005).toFixed(2) === "1.00"`` behavior.
    """
    from decimal import Decimal, ROUND_HALF_UP

    if x != x or x in (float("inf"), float("-inf")):
        return x
    quantum = Decimal(1).scaleb(-precision)
    d = Decimal(x).quantize(quantum, rounding=ROUND_HALF_UP)
    return float(d)


def _js_round(x: float) -> float:
    """JavaScript ``Math.round``: round half *up* (toward +Infinity)."""
    import math

    return math.floor(x + 0.5)
