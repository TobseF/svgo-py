"""Public ``optimize`` entry point. Port of ``lib/svgo.js``."""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional

from .builtin import get_plugin
from .engine import invoke_plugins
from .parser import parse_svg
from .stringifier import stringify_svg
from .tools import encode_svg_datauri

VERSION = "4.1.0"


def _resolve_plugin_config(plugin) -> Optional[Dict[str, Any]]:
    if isinstance(plugin, str):
        builtin = get_plugin(plugin)
        if builtin is None:
            raise ValueError(f'Unknown builtin plugin "{plugin}" specified.')
        return {"name": plugin, "params": {}, "fn": builtin["fn"]}
    if isinstance(plugin, dict) and plugin is not None:
        if plugin.get("name") is None:
            raise ValueError("Plugin name must be specified")
        fn = plugin.get("fn")
        if fn is None:
            builtin = get_plugin(plugin["name"])
            if builtin is None:
                raise ValueError(f"Unknown builtin plugin \"{plugin['name']}\" specified.")
            fn = builtin["fn"]
        return {"name": plugin["name"], "params": plugin.get("params"), "fn": fn}
    return None


def optimize(input_str: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if config is None:
        config = {}
    if not isinstance(config, dict):
        raise ValueError("Config should be an object")

    max_pass_count = 10 if config.get("multipass") else 1
    prev_result_size = float("inf")
    output = ""
    info: Dict[str, Any] = {}
    if config.get("path") is not None:
        info["path"] = config["path"]

    for i in range(max_pass_count):
        info["multipassCount"] = i
        ast = parse_svg(input_str, config.get("path"))
        # NOTE: JS uses `config.plugins || [...]`; an empty array is truthy in
        # JS, so it must be preserved (do not fall back to preset-default).
        plugins = config["plugins"] if config.get("plugins") is not None else ["preset-default"]
        if not isinstance(plugins, list):
            raise ValueError("malformed config, `plugins` property must be an array.")
        resolved = [_resolve_plugin_config(p) for p in plugins if p is not None]

        global_overrides: Dict[str, Any] = {}
        if config.get("floatPrecision") is not None:
            global_overrides["floatPrecision"] = config["floatPrecision"]

        invoke_plugins(ast, info, resolved, None, global_overrides)
        output = stringify_svg(ast, config.get("js2svg"))
        if len(output) < prev_result_size:
            input_str = output
            prev_result_size = len(output)
        else:
            break

    if config.get("datauri"):
        output = encode_svg_datauri(output, config["datauri"])
    return {"data": output}
