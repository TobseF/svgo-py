# svgo (pure-Python port)

A pure-Python reimplementation of [SVGO](https://github.com/svg/svgo) (SVG
Optimizer). It optimizes/minifies SVG documents **without a JavaScript
interpreter** so it can be embedded directly into Python projects.

Ported from SVGO **4.1.0**.

## Installation

```bash
pip install .          # from this directory
# runtime dependencies: tinycss2, cssselect (pure Python)
```

## Usage (library)

```python
from svgo import optimize

svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect x="1" y="2" width="3" height="4"/></svg>'
result = optimize(svg)
print(result["data"])
# -> <svg xmlns="http://www.w3.org/2000/svg"><path d="M1 2h3v4H1z"/></svg>
```

`optimize(input, config)` mirrors the JavaScript API and returns a dict
`{"data": <optimized svg string>}`.

### Configuration

```python
optimize(svg, {
    "multipass": True,               # run repeatedly until no further gain
    "floatPrecision": 2,             # global numeric precision override
    "js2svg": {"pretty": True, "indent": 2},
    "plugins": ["preset-default"],   # default when omitted
    "datauri": "base64",             # wrap output as a data: URI
})
```

Selecting/overriding plugins works exactly like SVGO:

```python
optimize(svg, {
    "plugins": [
        {
            "name": "preset-default",
            "params": {
                "overrides": {
                    "removeXMLProcInst": False,
                    "removeDesc": {"removeAny": True},
                },
            },
        },
    ],
})
```

Individual plugins can also be listed by name, e.g.
`{"plugins": ["removeComments", "convertColors"]}`.

## Usage (CLI)

```bash
pysvgo input.svg -o output.svg
pysvgo input.svg --pretty --indent 2
cat in.svg | pysvgo - -o -
```

## Scope

This port implements the full **`preset-default`** pipeline — the 33 plugins
SVGO runs by default:

`removeDoctype, removeXMLProcInst, removeComments, removeDeprecatedAttrs,
removeMetadata, removeEditorsNSData, cleanupAttrs, mergeStyles, inlineStyles,
minifyStyles, cleanupIds, removeUselessDefs, cleanupNumericValues,
convertColors, removeUnknownsAndDefaults, removeNonInheritableGroupAttrs,
removeUselessStrokeAndFill, cleanupEnableBackground, removeHiddenElems,
removeEmptyText, convertShapeToPath, convertEllipseToCircle,
moveElemsAttrsToGroup, moveGroupAttrsToElems, collapseGroups, convertPathData,
convertTransform, removeEmptyAttrs, removeEmptyContainers, mergePaths,
removeUnusedNS, sortAttrs, sortDefsChildren, removeDesc`

The full path-data optimizer (`convertPathData`, including curve→arc detection),
the transform engine (`convertTransform`, matrix decomposition), path merging
with GJK hull-intersection, the CSS cascade / selector engine used by
`inlineStyles`, `removeHiddenElems`, etc. are all implemented natively.

### Known limitation: `minifyStyles`

SVGO uses the JavaScript [`csso`](https://github.com/css/csso) library for CSS
minification. There is no pure-Python equivalent, so `minifyStyles` (and the CSS
minification `inlineStyles` performs on remaining `<style>` content and `style`
attributes) performs **whitespace/comment-level minification only**. It does
**not** reproduce csso's value-level and structural optimizations:

* color minification (`black` → `#000`, `0.5` → `.5`),
* shorthand merging (`padding-top/right/bottom/left` → `padding`),
* usage-based dead-rule elimination,
* rule restructuring.

Everything else in the pipeline matches the reference byte-for-byte. In a
differential test over the project's fixture corpus, **every** remaining
difference versus reference SVGO is attributable to this CSS-value minification
inside `<style>` / `style` attributes; there are no structural differences.

## Tests

```bash
pip install pytest
pytest
```

The test suite reuses SVGO's own language-agnostic plugin fixtures
(`*.svg.txt`, `input @@@ expected @@@ params`) plus ports of the core
`path` / `parser` / `xast` tests and end-to-end snapshots captured from the
reference implementation. Fixtures that depend on csso-specific behavior are
marked `xfail` with a documented reason.

## Release (PyPI)

Requires `build` and `twine` (`pip install build twine`) and a configured
`~/.pypirc` with a PyPI API token.

```bash
python -m build              # builds dist/*.tar.gz and dist/*.whl
python -m twine check dist/* # validates package metadata
python -m twine upload dist/*  # uploads to PyPI
```

## License

MIT (same as SVGO).
