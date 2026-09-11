"""SVG element / attribute / color data tables.

Port of ``plugins/_collections.js``. The data is generated once from the
upstream JavaScript source (serialized to ``data/collections.json``) and
revived here into native Python ``set``/``dict`` structures. This guarantees
byte-for-byte fidelity with the reference tables without hand-transcription.
"""

from __future__ import annotations

import json
from typing import Any

try:  # Python 3.9+: importlib.resources.files
    from importlib.resources import files as _files

    _RAW = json.loads(
        _files("svgo.data").joinpath("collections.json").read_text(encoding="utf-8")
    )
except Exception:  # pragma: no cover - fallback for exotic layouts
    import os

    _path = os.path.join(os.path.dirname(__file__), "data", "collections.json")
    with open(_path, encoding="utf-8") as _fh:
        _RAW = json.load(_fh)


def _revive(value: Any) -> Any:
    if isinstance(value, dict):
        if "__set__" in value and len(value) == 1:
            return set(_revive(v) for v in value["__set__"])
        if "__map__" in value and len(value) == 1:
            return {_revive(k): _revive(v) for k, v in value["__map__"]}
        return {k: _revive(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_revive(v) for v in value]
    return value


_DATA = {k: _revive(v) for k, v in _RAW.items()}

attrsGroups = _DATA["attrsGroups"]
attrsGroupsDefaults = _DATA["attrsGroupsDefaults"]
attrsGroupsDeprecated = _DATA["attrsGroupsDeprecated"]
colorsNames = _DATA["colorsNames"]
colorsProps = _DATA["colorsProps"]
colorsShortNames = _DATA["colorsShortNames"]
editorNamespaces = _DATA["editorNamespaces"]
elems = _DATA["elems"]
elemsGroups = _DATA["elemsGroups"]
inheritableAttrs = _DATA["inheritableAttrs"]
pathElems = _DATA["pathElems"]
presentationNonInheritableGroupAttrs = _DATA["presentationNonInheritableGroupAttrs"]
pseudoClasses = _DATA["pseudoClasses"]
referencesProps = _DATA["referencesProps"]
textElems = _DATA["textElems"]

__all__ = list(_DATA.keys())
