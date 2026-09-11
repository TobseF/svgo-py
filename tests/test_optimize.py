"""End-to-end tests for the full default preset and the public API.

Expected outputs were produced by the reference JavaScript SVGO 4.1.0 and are
embedded here so the tests need no Node.js at runtime.
"""

from svgo import VERSION, optimize


def test_version():
    assert VERSION == "4.1.0"


def test_default_preset_snapshot():
    svg = """
    <?xml version="1.0" encoding="utf-8"?>
    <svg viewBox="0 0 120 120">
      <desc>
        Created with love
      </desc>
      <circle fill="#ff0000" cx="60" cy="60" r="50"/>
    </svg>
  """
    result = optimize(svg, {"plugins": ["preset-default"], "js2svg": {"pretty": True, "indent": 2}})
    assert result["data"] == (
        '<svg viewBox="0 0 120 120">\n' "  <circle cx=\"60\" cy=\"60\" r=\"50\" fill=\"red\"/>\n" "</svg>\n"
    )


def test_preset_overrides():
    svg = """
    <?xml version="1.0" encoding="utf-8"?>
    <svg viewBox="0 0 120 120">
      <desc>
        Not standard description
      </desc>
      <circle fill="#ff0000" cx="60" cy="60" r="50"/>
    </svg>
  """
    result = optimize(
        svg,
        {
            "plugins": [
                {
                    "name": "preset-default",
                    "params": {
                        "overrides": {
                            "removeXMLProcInst": False,
                            "removeDesc": {"removeAny": True},
                        }
                    },
                }
            ],
            "js2svg": {"pretty": True, "indent": 2},
        },
    )
    assert result["data"] == (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<svg viewBox="0 0 120 120">\n'
        '  <circle cx="60" cy="60" r="50" fill="red"/>\n'
        "</svg>\n"
    )


# (input, expected) pairs captured from reference SVGO 4.1.0 with default config.
_SNAPSHOTS = [
    (
        '<svg xmlns="http://www.w3.org/2000/svg"><rect x="1" y="2" width="3" height="4"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><path d="M1 2h3v4H1z"/></svg>',
    ),
    (
        '<svg xmlns="http://www.w3.org/2000/svg"><g><g><path d="M10 10 L 20 20 L 30 10"/></g></g></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><path d="m10 10 10 10 10-10"/></svg>',
    ),
    (
        '<svg xmlns="http://www.w3.org/2000/svg"><circle cx="10" cy="10" r="5" fill="#FF0000"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><circle cx="10" cy="10" r="5" fill="red"/></svg>',
    ),
    (
        '<svg xmlns="http://www.w3.org/2000/svg"><ellipse cx="10" cy="10" rx="5" ry="5"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><circle cx="10" cy="10" r="5"/></svg>',
    ),
    (
        '<svg xmlns="http://www.w3.org/2000/svg"><!-- c --><metadata>x</metadata><rect width="10" height="10"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0h10v10H0z"/></svg>',
    ),
    (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M 10.0000 20.5000 C 30 40 50 60 70 80" transform="translate(10,10)"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M20 30.5C40 50 60 70 80 90"/></svg>',
    ),
    (
        '<svg xmlns="http://www.w3.org/2000/svg"><polygon points="10,10 20,10 20,20 10,20"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><path d="M10 10h10v10H10z"/></svg>',
    ),
    (
        '<svg xmlns="http://www.w3.org/2000/svg"><g transform="scale(2)"><path d="M0 0 L10 10" transform="rotate(45)"/></g></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0v28.284"/></svg>',
    ),
]


import pytest


@pytest.mark.parametrize("inp,expected", _SNAPSHOTS)
def test_default_preset_pipeline(inp, expected):
    assert optimize(inp, {})["data"] == expected


def test_multipass_reduces_or_stops():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><g><g><rect width="10" height="10"/></g></g></svg>'
    once = optimize(svg, {})["data"]
    multi = optimize(svg, {"multipass": True})["data"]
    assert len(multi) <= len(once)


def test_datauri_base64():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'
    result = optimize(svg, {"datauri": "base64"})
    assert result["data"].startswith("data:image/svg+xml;base64,")


def test_empty_plugins_roundtrip():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'
    assert optimize(svg, {"plugins": []})["data"] == svg
