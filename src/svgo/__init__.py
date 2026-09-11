"""Pure-Python reimplementation of SVGO (SVG Optimizer).

Usage::

    from svgo import optimize
    result = optimize(svg_string)
    print(result["data"])
"""

from ._optimize import VERSION, optimize
from .builtin import get_plugin
from .parser import parse_svg
from .stringifier import stringify_svg

__all__ = ["optimize", "VERSION", "get_plugin", "parse_svg", "stringify_svg"]
