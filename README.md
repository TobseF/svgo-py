# svgo-py

[![PyPI version](https://img.shields.io/pypi/v/svgo-py.svg)](https://pypi.org/project/svgo-py/)
[![Python versions](https://img.shields.io/pypi/pyversions/svgo-py.svg)](https://pypi.org/project/svgo-py/)
[![License: MIT](https://img.shields.io/pypi/l/svgo-py.svg)](https://github.com/TobseF/svgo-py/blob/main/LICENSE)

**Optimize and minify SVG files in pure Python. No Node.js, no npm, no JavaScript runtime.**

`svgo-py` is a faithful Python port of [SVGO](https://github.com/svg/svgo) **4.1.0**,
the de-facto standard SVG optimizer. It uses the same plugins, the same configuration
format and the same output, as a regular Python package.

```python
from svgo import optimize

optimize('<svg xmlns="http://www.w3.org/2000/svg"><rect x="1" y="2" width="3" height="4"/></svg>')["data"]
# '<svg xmlns="http://www.w3.org/2000/svg"><path d="M1 2h3v4H1z"/></svg>'
```

## Why svgo-py?

- **No JavaScript toolchain.** Optimize SVGs inside Python apps, build scripts, CI jobs
  and containers without installing Node.js or shelling out to `npx svgo`.
- **Same results as SVGO.** Tested against SVGO's own plugin fixtures and against
  snapshots taken from the reference implementation.
- **All 53 SVGO plugins**, including the full `preset-default` pipeline.
- **Works with your SVGO configs.** The config dict has the same structure as
  `svgo.config.js`, so existing setups carry over.
- **Runs anywhere Python runs.** A single pure-Python wheel (`py3-none-any`) for Windows,
  macOS and Linux on x86 and ARM. Only two small pure-Python dependencies
  ([`tinycss2`](https://pypi.org/project/tinycss2/), [`cssselect`](https://pypi.org/project/cssselect/)).
- **Library and CLI.** Call `optimize()` from code, or use the `pysvgo` command.
- **Typed.** Ships a `py.typed` marker for editors and type checkers.

## Installation

Requires **Python 3.9 or newer**.

```bash
pip install svgo-py
```

> **Note:**
> The package is called **`svgo-py`** on PyPI, but you import it as **`svgo`**:
> `from svgo import optimize`.

### Platform-specific setup

Installing into a virtual environment is recommended on every platform. On newer
Linux distributions and on Homebrew Python, `pip install` into the system Python is
blocked (`externally-managed-environment`), so a virtual environment is required there.

<table>
<tr><th>Windows (PowerShell)</th><th>macOS / Linux</th></tr>
<tr>
<td>

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install svgo-py
```

</td>
<td>

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install svgo-py
```

</td>
</tr>
</table>

Platform notes:

- **Windows:** In `cmd.exe`, activate with `.venv\Scripts\activate.bat`. If PowerShell
  refuses to run the activation script, run
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
- **Windows:** If `pysvgo` is "not recognized" after a global install, the Python
  `Scripts` folder is not on your `PATH`. Use `python -m svgo.cli` instead, or install with
  `pipx` (see below).
- **Linux (Debian/Ubuntu):** If `venv` is missing, install it with
  `sudo apt install python3-venv`.

### Other package managers

| Tool                       | Command                         |
|----------------------------|---------------------------------|
| uv                         | `uv add svgo-py`                |
| Poetry                     | `poetry add svgo-py`            |
| pipx (CLI only, isolated)  | `pipx install svgo-py`          |
| requirements.txt           | `svgo-py>=4.1,<5`               |
| pyproject.toml             | `dependencies = ["svgo-py>=4.1,<5"]` |

`pipx` is the easiest way to get a global `pysvgo` command on all three platforms
without touching your system Python.

### Release files and offline install

All release files are available on PyPI: **<https://pypi.org/project/svgo-py/#files>**
(older versions: [release history](https://pypi.org/project/svgo-py/#history)).

| File | Type |
|------|------|
| [`svgo_py-4.1.0.1-py3-none-any.whl`](https://files.pythonhosted.org/packages/e0/80/68580148a3673a6023692fd4418ab44c2021abc92f9bb0ff1ca832c3d56e/svgo_py-4.1.0.1-py3-none-any.whl) | Wheel, all platforms |
| [`svgo_py-4.1.0.1.tar.gz`](https://files.pythonhosted.org/packages/a8/70/c280e76a202db3c967794a2e24e1b1f4f3c93f244345ce65a34257c8a289/svgo_py-4.1.0.1.tar.gz) | Source distribution |

To install a downloaded wheel:

```bash
pip install svgo_py-4.1.0.1-py3-none-any.whl
```

For machines without internet access, download the package together with its
dependencies on a connected machine and copy the folder over:

```bash
pip download svgo-py -d wheels
pip install --no-index --find-links wheels svgo-py
```

### From the GitHub repository

To try the latest unreleased code:

```bash
pip install "git+https://github.com/TobseF/svgo-py.git"
```

### Check the installation

```bash
python -c "import svgo; print(svgo.VERSION)"
pysvgo --version
```

Both should print `4.1.0`, the SVGO version this port is based on. The package version
adds a fourth number for port revisions (e.g. `4.1.0.1`).

## Quick start

### In Python

```python
from svgo import optimize

with open("logo.svg", encoding="utf-8") as f:
    result = optimize(f.read(), {"multipass": True})

with open("logo.min.svg", "w", encoding="utf-8") as f:
    f.write(result["data"])
```

`optimize(input, config=None)` mirrors the JavaScript API and returns a dict
`{"data": <optimized SVG string>}`.

Optimize a whole folder:

```python
from pathlib import Path
from svgo import optimize

for svg in Path("icons").rglob("*.svg"):
    svg.write_text(optimize(svg.read_text(encoding="utf-8"))["data"], encoding="utf-8")
```

### On the command line

```bash
pysvgo input.svg -o output.svg     # write to a new file
pysvgo input.svg                   # optimize in place
pysvgo input.svg --pretty --indent 2
pysvgo input.svg --multipass -p 2  # several passes, 2-digit precision
```

| Option | Description |
|--------|-------------|
| `input` | Input file, or `-` for stdin (default) |
| `-o`, `--output` | Output file, or `-` for stdout. Defaults to overwriting the input |
| `-p`, `--precision` | Float precision passed to plugins |
| `--multipass` | Optimize repeatedly until no further gain |
| `--pretty`, `--indent N` | Pretty-print the output (default indent 4) |
| `--datauri {base64,enc,unenc}` | Emit the result as a `data:` URI |
| `--version` | Print the version |

Pipes and batch processing differ slightly between shells:

<table>
<tr><th>Windows (PowerShell)</th><th>macOS / Linux (bash, zsh)</th></tr>
<tr>
<td>

```powershell
# stdin -> stdout
Get-Content in.svg -Raw | pysvgo - -o -

# every SVG in a folder, in place
Get-ChildItem icons -Filter *.svg -Recurse |
  ForEach-Object { pysvgo $_.FullName }
```

</td>
<td>

```bash
# stdin -> stdout
cat in.svg | pysvgo - -o -

# every SVG in a folder, in place
find icons -name '*.svg' -exec pysvgo {} \;
```

</td>
</tr>
</table>

## Configuration

The configuration has the same structure as SVGO's `svgo.config.js`:

```python
optimize(svg, {
    "multipass": True,                       # run repeatedly until no further gain
    "floatPrecision": 2,                     # global numeric precision override
    "js2svg": {"pretty": True, "indent": 2}, # output formatting
    "plugins": ["preset-default"],           # the default when omitted
    "datauri": "base64",                     # wrap output as a data: URI
})
```

Override or disable plugins of the default preset, and add extra plugins:

```python
optimize(svg, {
    "plugins": [
        {
            "name": "preset-default",
            "params": {
                "overrides": {
                    "removeComments": False,              # disable a plugin
                    "cleanupIds": {"minify": False},       # change a plugin's params
                },
            },
        },
        "removeDimensions",                               # add a non-default plugin
        {"name": "prefixIds", "params": {"prefix": "icon"}},
    ],
})
```

Plugin names and parameters are the same as in SVGO, so the
[SVGO plugin documentation](https://svgo.dev/docs/plugins/) applies directly.
`svgo.builtin_plugins()` returns the full list of available plugins.

## Common use cases

- Shrinking icons and illustrations exported from Figma, Illustrator, Inkscape or Sketch
- Build steps for static site generators and documentation tools (MkDocs, Sphinx, Pelican, ...)
- Normalizing SVG uploads in Django, Flask or FastAPI apps
- Generating inline SVGs or `data:` URIs for HTML and CSS
- CI checks or pre-commit hooks that keep SVG assets small

> **Important:**
> Like SVGO, this is an optimizer, not a security sanitizer. Plugins such as
> `removeScripts` reduce content, but do not rely on them to make untrusted SVGs safe.

## Plugins and compatibility

This port implements **all 53 built-in SVGO plugins**: the complete
**`preset-default`** pipeline (33 plugins) and every optional plugin. The path-data
optimizer (`convertPathData`, including curve-to-arc detection), the transform engine
(`convertTransform`, matrix decomposition), path merging with GJK hull intersection and
the CSS cascade and selector engine are all implemented natively in Python.

<details>
<summary>Optional plugins (not part of <code>preset-default</code>)</summary>

`addAttributesToSVGElement`, `addClassesToSVGElement`, `cleanupListOfValues`,
`convertOneStopGradients`, `convertStyleToAttrs`, `prefixIds`,
`removeAttributesBySelector`, `removeAttrs`, `removeDimensions`,
`removeElementsByAttr`, `removeOffCanvasPaths`, `removeRasterImages`, `removeScripts`,
`removeStyleElement`, `removeTitle`, `removeViewBox`, `removeXMLNS`, `removeXlink`,
`reusePaths`

</details>

<details>
<summary>Known differences to SVGO: CSS minification (<code>minifyStyles</code>)</summary>

SVGO uses the JavaScript library [csso](https://github.com/css/csso) for CSS
minification, which has no Python equivalent. This port reproduces csso's
**whitespace and comment removal** and **value-level minification**:

- color minification: `black` → `#000`, `#FFFFFF` → `#fff` (also inside functions such
  as `linear-gradient(...)`)
- number minification: `0.5` → `.5`, `1.50` → `1.5`
- `url("#x")` → `url(#x)` unquoting
- dropping empty rules
- custom properties (`--Foo`) are preserved case-sensitively and left untouched

It does **not** reproduce csso's **structural** optimizations:

- shorthand merging (`padding-top/right/bottom/left` → `padding`)
- usage-based dead-rule elimination (removing rules whose selectors match no element)
- duplicate-selector and rule restructuring
- a few csstree-specific at-rule serialization details

In a differential test over the fixture corpus, **every** remaining difference from
reference SVGO comes from one of these structural CSS passes inside `<style>` elements
or `style` attributes. Everything else produces the same output. In practice the
affected SVGs are slightly larger than with SVGO, but still valid and visually
identical.

</details>

## Development and testing

Clone the repository and install it in editable mode with the test extras:

<table>
<tr><th>Windows (PowerShell)</th><th>macOS / Linux</th></tr>
<tr>
<td>

```powershell
git clone https://github.com/TobseF/svgo-py.git
cd svgo-py
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[test]"
pytest
```

</td>
<td>

```bash
git clone https://github.com/TobseF/svgo-py.git
cd svgo-py
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
pytest
```

</td>
</tr>
</table>

The test suite reuses SVGO's own language-agnostic plugin fixtures
(`*.svg.txt`, `input @@@ expected @@@ params`), ports of the core `path`, `parser` and
`xast` tests, and end-to-end snapshots captured from the reference implementation.
Fixtures that depend on csso-specific behavior are marked `xfail` with a documented
reason. The whole suite runs in about a second.

<details>
<summary>Publishing a release (maintainers)</summary>

Requires `build` and `twine` (`pip install build twine`) and a `~/.pypirc` with a PyPI
API token.

```bash
python -m build                # builds dist/*.tar.gz and dist/*.whl
python -m twine check dist/*   # validates package metadata
python -m twine upload dist/*  # uploads to PyPI
```

</details>

## Contributing

Bug reports and pull requests are welcome on
[GitHub](https://github.com/TobseF/svgo-py/issues). If an SVG is optimized differently
than by SVGO 4.1.0, please attach the input file and both outputs. That makes
differences easy to reproduce and turn into a test fixture.

## Credits

All optimization logic is ported from [SVGO](https://github.com/svg/svgo) by its
authors and contributors. This project would not exist without their work.

## License

[MIT](https://github.com/TobseF/svgo-py/blob/main/LICENSE), the same license as SVGO.
