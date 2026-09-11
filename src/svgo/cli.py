"""Minimal command-line interface for the pure-Python SVGO port.

Usage::

    pysvgo input.svg -o output.svg
    pysvgo input.svg            # writes input.svg in place
    cat in.svg | pysvgo - -o -  # stdin to stdout
    pysvgo in.svg --pretty
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from ._optimize import VERSION, optimize


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="pysvgo", description="Optimize/minify SVG (pure-Python SVGO port).")
    parser.add_argument("input", nargs="?", default="-", help="Input SVG file, or '-' for stdin.")
    parser.add_argument("-o", "--output", help="Output file, or '-' for stdout. Defaults to overwriting input.")
    parser.add_argument("-p", "--precision", type=int, help="Float precision passed to plugins.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the output.")
    parser.add_argument("--indent", type=int, default=4, help="Indent width when pretty printing (default 4).")
    parser.add_argument("--multipass", action="store_true", help="Optimize repeatedly until no further gain.")
    parser.add_argument("--datauri", choices=["base64", "enc", "unenc"], help="Emit output as a data: URI.")
    parser.add_argument("--version", action="version", version=f"pysvgo {VERSION}")
    args = parser.parse_args(argv)

    if args.input == "-":
        data = sys.stdin.read()
        default_output = "-"
    else:
        with open(args.input, encoding="utf-8") as fh:
            data = fh.read()
        default_output = args.input

    config = {
        "multipass": args.multipass,
        "js2svg": {"pretty": args.pretty, "indent": args.indent},
    }
    if args.precision is not None:
        config["floatPrecision"] = args.precision
    if args.datauri:
        config["datauri"] = args.datauri
    if args.input != "-":
        config["path"] = args.input

    result = optimize(data, config)
    output = args.output if args.output is not None else default_output

    if output == "-":
        sys.stdout.write(result["data"])
    else:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(result["data"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
