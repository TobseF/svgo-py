"""Built-in plugin registry. Port of ``lib/builtin.js`` (default-preset subset).

Plugins are imported lazily by name from :mod:`svgo.plugins` so that the
package can be developed and tested incrementally.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, List, Optional

# Plugins that make up preset-default, in execution order.
PRESET_DEFAULT_PLUGINS: List[str] = [
    "removeDoctype",
    "removeXMLProcInst",
    "removeComments",
    "removeDeprecatedAttrs",
    "removeMetadata",
    "removeEditorsNSData",
    "cleanupAttrs",
    "mergeStyles",
    "inlineStyles",
    "minifyStyles",
    "cleanupIds",
    "removeUselessDefs",
    "cleanupNumericValues",
    "convertColors",
    "removeUnknownsAndDefaults",
    "removeNonInheritableGroupAttrs",
    "removeUselessStrokeAndFill",
    "cleanupEnableBackground",
    "removeHiddenElems",
    "removeEmptyText",
    "convertShapeToPath",
    "convertEllipseToCircle",
    "moveElemsAttrsToGroup",
    "moveGroupAttrsToElems",
    "collapseGroups",
    "convertPathData",
    "convertTransform",
    "removeEmptyAttrs",
    "removeEmptyContainers",
    "mergePaths",
    "removeUnusedNS",
    "sortAttrs",
    "sortDefsChildren",
    "removeDesc",
]

_ALIASES = {
    # removeScriptElement was renamed to removeScripts
    "removeScriptElement": "removeScripts",
}

_cache: Dict[str, Dict[str, Any]] = {}


def _load_plugin_module(name: str):
    return importlib.import_module(f".plugins.{name}", package="svgo")


def _builtin_plugin(name: str) -> Optional[Dict[str, Any]]:
    if name in _cache:
        return _cache[name]
    try:
        module = _load_plugin_module(name)
    except ModuleNotFoundError:
        return None
    plugin = {
        "name": getattr(module, "name", name),
        "description": getattr(module, "description", ""),
        "fn": module.fn,
    }
    _cache[name] = plugin
    return plugin


def _preset_default() -> Dict[str, Any]:
    if "preset-default" in _cache:
        return _cache["preset-default"]
    from .engine import create_preset

    plugins = []
    for pname in PRESET_DEFAULT_PLUGINS:
        builtin = _builtin_plugin(pname)
        if builtin is None:
            raise ImportError(f"preset-default plugin not implemented: {pname}")
        plugins.append({"name": builtin["name"], "params": {}, "fn": builtin["fn"]})
    preset = create_preset("preset-default", plugins)
    _cache["preset-default"] = preset
    return preset


def get_plugin(name: str) -> Optional[Dict[str, Any]]:
    if name == "preset-default":
        return _preset_default()
    if name in _ALIASES:
        name = _ALIASES[name]
    return _builtin_plugin(name)
