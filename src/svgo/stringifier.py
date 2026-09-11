"""XAST -> SVG string. Port of ``lib/stringifier.js``."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from .collections import textElems

_ENTITIES = {
    "&": "&amp;",
    "'": "&apos;",
    '"': "&quot;",
    ">": "&gt;",
    "<": "&lt;",
}

_DEFAULTS: Dict[str, Any] = {
    "doctypeStart": "<!DOCTYPE",
    "doctypeEnd": ">",
    "procInstStart": "<?",
    "procInstEnd": "?>",
    "tagOpenStart": "<",
    "tagOpenEnd": ">",
    "tagCloseStart": "</",
    "tagCloseEnd": ">",
    "tagShortStart": "<",
    "tagShortEnd": "/>",
    "attrStart": '="',
    "attrEnd": '"',
    "commentStart": "<!--",
    "commentEnd": "-->",
    "cdataStart": "<![CDATA[",
    "cdataEnd": "]]>",
    "textStart": "",
    "textEnd": "",
    "indent": 4,
    "regEntities": re.compile(r"[&'\"<>]"),
    "regValEntities": re.compile(r"[&\"<>]"),
    "pretty": False,
    "useShortTags": True,
    "eol": "lf",
    "finalNewline": False,
}


def _encode_entity(match: "re.Match[str]") -> str:
    return _ENTITIES[match.group(0)]


class _State:
    __slots__ = ("indent", "text_context", "indent_level")

    def __init__(self, indent: str):
        self.indent = indent
        self.text_context = None
        self.indent_level = 0


def stringify_svg(data, user_options: Optional[Dict[str, Any]] = None) -> str:
    config = dict(_DEFAULTS)
    if user_options:
        config.update(user_options)

    indent = config["indent"]
    new_indent = "    "
    if isinstance(indent, bool):
        # bool is subclass of int; treat like JS "not a number" fallthrough
        pass
    elif isinstance(indent, (int, float)):
        new_indent = "\t" if indent < 0 else " " * int(indent)
    elif isinstance(indent, str):
        new_indent = indent

    state = _State(new_indent)
    eol = "\r\n" if config["eol"] == "crlf" else "\n"
    if config["pretty"]:
        for key in (
            "doctypeEnd",
            "procInstEnd",
            "commentEnd",
            "cdataEnd",
            "tagShortEnd",
            "tagOpenEnd",
            "tagCloseEnd",
            "textEnd",
        ):
            config[key] = config[key] + eol

    svg = _stringify_node(data, config, state)
    if config["finalNewline"] and len(svg) > 0 and not svg.endswith("\n"):
        svg += eol
    return svg


def _stringify_node(data, config, state) -> str:
    svg = []
    state.indent_level += 1
    for item in data.children:
        t = item.type
        if t == "element":
            svg.append(_stringify_element(item, config, state))
        elif t == "text":
            svg.append(_stringify_text(item, config, state))
        elif t == "doctype":
            svg.append(_stringify_doctype(item, config))
        elif t == "instruction":
            svg.append(_stringify_instruction(item, config))
        elif t == "comment":
            svg.append(_stringify_comment(item, config))
        elif t == "cdata":
            svg.append(_stringify_cdata(item, config, state))
    state.indent_level -= 1
    return "".join(svg)


def _create_indent(config, state) -> str:
    if config["pretty"] and state.text_context is None:
        return state.indent * (state.indent_level - 1)
    return ""


def _stringify_doctype(node, config) -> str:
    return config["doctypeStart"] + node.data["doctype"] + config["doctypeEnd"]


def _stringify_instruction(node, config) -> str:
    return config["procInstStart"] + node.name + " " + node.value + config["procInstEnd"]


def _stringify_comment(node, config) -> str:
    return config["commentStart"] + node.value + config["commentEnd"]


def _stringify_cdata(node, config, state) -> str:
    return _create_indent(config, state) + config["cdataStart"] + node.value + config["cdataEnd"]


def _stringify_element(node, config, state) -> str:
    if len(node.children) == 0:
        if config["useShortTags"]:
            return (
                _create_indent(config, state)
                + config["tagShortStart"]
                + node.name
                + _stringify_attributes(node, config)
                + config["tagShortEnd"]
            )
        return (
            _create_indent(config, state)
            + config["tagShortStart"]
            + node.name
            + _stringify_attributes(node, config)
            + config["tagOpenEnd"]
            + config["tagCloseStart"]
            + node.name
            + config["tagCloseEnd"]
        )

    tag_open_start = config["tagOpenStart"]
    tag_open_end = config["tagOpenEnd"]
    tag_close_start = config["tagCloseStart"]
    tag_close_end = config["tagCloseEnd"]
    open_indent = _create_indent(config, state)
    close_indent = _create_indent(config, state)

    if state.text_context:
        tag_open_start = _DEFAULTS["tagOpenStart"]
        tag_open_end = _DEFAULTS["tagOpenEnd"]
        tag_close_start = _DEFAULTS["tagCloseStart"]
        tag_close_end = _DEFAULTS["tagCloseEnd"]
        open_indent = ""
    elif node.name in textElems:
        tag_open_end = _DEFAULTS["tagOpenEnd"]
        tag_close_start = _DEFAULTS["tagCloseStart"]
        close_indent = ""
        state.text_context = node

    children = _stringify_node(node, config, state)

    if state.text_context is node:
        state.text_context = None

    return (
        open_indent
        + tag_open_start
        + node.name
        + _stringify_attributes(node, config)
        + tag_open_end
        + children
        + close_indent
        + tag_close_start
        + node.name
        + tag_close_end
    )


def _stringify_attributes(node, config) -> str:
    attrs = []
    for name, value in node.attributes.items():
        attrs.append(" " + name)
        if value is not None:
            encoded = config["regValEntities"].sub(_encode_entity, str(value))
            attrs.append(config["attrStart"] + encoded + config["attrEnd"])
    return "".join(attrs)


def _stringify_text(node, config, state) -> str:
    return (
        _create_indent(config, state)
        + config["textStart"]
        + config["regEntities"].sub(_encode_entity, node.value)
        + ("" if state.text_context else config["textEnd"])
    )
