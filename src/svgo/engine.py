"""Plugin engine + preset machinery. Port of ``lib/svgo/plugins.js``."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .visit import visit


def invoke_plugins(
    ast,
    info: Dict[str, Any],
    plugins: List[Dict[str, Any]],
    overrides: Optional[Dict[str, Any]],
    global_overrides: Dict[str, Any],
) -> None:
    for plugin in plugins:
        override = overrides.get(plugin["name"]) if overrides else None
        if override is False:
            continue
        params = {**(plugin.get("params") or {}), **global_overrides}
        if isinstance(override, dict):
            params.update(override)

        visitor = plugin["fn"](ast, params, info)
        if visitor is not None:
            visit(ast, visitor)


def create_preset(name: str, plugins: List[Dict[str, Any]]) -> Dict[str, Any]:
    plugin_names = [p["name"] for p in plugins]

    def fn(ast, params, info):
        float_precision = params.get("floatPrecision")
        overrides = params.get("overrides")
        global_overrides: Dict[str, Any] = {}
        if float_precision is not None:
            global_overrides["floatPrecision"] = float_precision
        if overrides:
            for plugin_name in overrides.keys():
                if plugin_name not in plugin_names:
                    import sys

                    print(
                        f"You are trying to configure {plugin_name} which is not part of {name}.",
                        file=sys.stderr,
                    )
        invoke_plugins(ast, info, plugins, overrides, global_overrides)
        return None

    return {
        "name": name,
        "isPreset": True,
        "plugins": plugins,
        "fn": fn,
    }
