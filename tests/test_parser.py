"""Port of ``lib/parser.test.js`` plus stringifier round-trips."""

from svgo.parser import parse_svg
from svgo.stringifier import stringify_svg


def test_text_preserved():
    input_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg">\n'
        '<text x="10" y="35" xml:space="preserve">\n'
        '    <a href="x">\n'
        "this is a test\n"
        "    </a>\n"
        "</text>\n"
        '<text x="10" y="35" xml:space="preserve">\n'
        "    <tspan>\n"
        "this is a test\n"
        "    </tspan>\n"
        "</text>\n"
        "</svg>"
    )
    expected = (
        '<svg xmlns="http://www.w3.org/2000/svg"><text x="10" y="35" xml:space="preserve">\n'
        '    <a href="x">\n'
        "this is a test\n"
        "    </a>\n"
        "</text><text x=\"10\" y=\"35\" xml:space=\"preserve\">\n"
        "    <tspan>\n"
        "this is a test\n"
        "    </tspan>\n"
        "</text></svg>"
    )
    assert stringify_svg(parse_svg(input_svg), {}) == expected


def test_entities_and_cdata_roundtrip():
    svg = '<svg><style>.a{fill:red}</style><![CDATA[ raw ]]>text &amp; more</svg>'
    assert stringify_svg(parse_svg(svg), {}) == svg


def test_comment_trimmed():
    svg = '<svg><!--  spaced  --><g/></svg>'
    assert stringify_svg(parse_svg(svg), {}) == '<svg><!--spaced--><g/></svg>'


def test_doctype_preserved():
    svg = (
        '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
        '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">'
        '<svg xmlns="http://www.w3.org/2000/svg"/>'
    )
    assert stringify_svg(parse_svg(svg), {}) == svg


def test_self_closing_short_tags():
    svg = '<svg><rect width="10" height="10"/></svg>'
    assert stringify_svg(parse_svg(svg), {}) == svg
