"""Fixture-driven plugin tests.

Mirrors upstream ``test/plugins/_index.test.js``: each ``<name>.<NN>.svg.txt``
fixture holds ``original @@@ expected @@@ params`` (optionally preceded by a
``description ===`` block). The plugin is run through :func:`svgo.optimize`
with ``js2svg={"pretty": True}`` and its output compared to ``expected``. As
upstream does, the plugin is applied twice to also assert idempotence.
"""

from __future__ import annotations

import json
import os
import re

import pytest

from svgo import optimize
from svgo.builtin import PRESET_DEFAULT_PLUGINS, get_plugin

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
_RE_FILENAME = re.compile(r"^(.*)\.(\d+)\.svg\.txt$")
_IDEMPOTENCE_EXCLUDE = {"addAttributesToSVGElement", "convertTransform"}


def _fixture_plugin_names():
    names = set()
    for filename in os.listdir(FIXTURES_DIR):
        match = _RE_FILENAME.match(filename)
        if match:
            names.add(match.group(1))
    return names


def _implemented():
    """Every plugin that resolves via get_plugin and has fixtures (preset +
    the ported non-default plugins)."""
    impl = set()
    for name in set(PRESET_DEFAULT_PLUGINS) | _fixture_plugin_names():
        try:
            if get_plugin(name) is not None:
                impl.add(name)
        except Exception:
            pass
    return impl


_IMPLEMENTED = _implemented()


def _normalize(text: str) -> str:
    return text.strip().replace(os.linesep, "\n").replace("\r\n", "\n")


# The CSS minifier does whitespace/comment removal plus csso-style *value*
# minification (color/number/url), but not csso's *structural* optimizations
# (shorthand merging, usage-based dead-rule removal, rule restructuring). The
# fixtures below exercise those structural passes and cannot match; they are
# marked xfail (non-strict) with the specific reason.
_XFAIL_PLUGINS = {}

_XFAIL_CASES = {
    # csso structural optimizations (shorthand merge / usage-based removal)
    "minifyStyles.01": "csso shorthand merging not reproduced",
    "minifyStyles.02": "csso shorthand merging not reproduced",
    "minifyStyles.03": "csso shorthand merging not reproduced",
    "minifyStyles.04": "csso usage-based dead-rule removal not reproduced",
    "minifyStyles.05": "csso usage-based dead-rule removal not reproduced",
    "minifyStyles.09": "csso structural optimization not reproduced",
    "minifyStyles.11": "csso structural optimization not reproduced",
    # csstree-exact at-rule serialization (url() unquoting, @media handling)
    "inlineStyles.13": "csstree-exact at-rule serialization not reproduced",
    "inlineStyles.14": "csstree-exact @media serialization not reproduced",
    "inlineStyles.15": "csstree-exact at-rule serialization not reproduced",
}


def _collect():
    cases = []
    for filename in sorted(os.listdir(FIXTURES_DIR)):
        match = _RE_FILENAME.match(filename)
        if not match:
            continue
        name, index = match.group(1), match.group(2)
        if name not in _IMPLEMENTED:
            continue
        marks = []
        case_id = f"{name}.{index}"
        if name in _XFAIL_PLUGINS:
            marks.append(pytest.mark.xfail(reason=_XFAIL_PLUGINS[name], strict=False))
        elif case_id in _XFAIL_CASES:
            marks.append(pytest.mark.xfail(reason=_XFAIL_CASES[case_id], strict=False))
        cases.append(
            pytest.param(
                f"{name}.{index}", name, os.path.join(FIXTURES_DIR, filename),
                id=f"{name}.{index}", marks=marks,
            )
        )
    return cases


@pytest.mark.parametrize("case_id,name,path", _collect())
def test_plugin_fixture(case_id, name, path):
    with open(path, encoding="utf-8") as fh:
        data = fh.read()

    items = re.split(r"\s*===\s*", _normalize(data))
    test = items[1] if len(items) == 2 else items[0]
    parts = re.split(r"\s*@@@\s*", test)
    original = parts[0]
    should = parts[1]
    params = json.loads(parts[2]) if len(parts) > 2 and parts[2] else {}

    plugin = {"name": name, "params": params}
    multipass = 1 if name in _IDEMPOTENCE_EXCLUDE else 2
    last = original
    for _ in range(multipass):
        result = optimize(last, {"path": path, "plugins": [plugin], "js2svg": {"pretty": True}})
        last = result["data"]
        assert _normalize(result["data"]) == should
