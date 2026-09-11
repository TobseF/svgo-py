"""SVG (XML) string -> XAST parser. Port of ``lib/parser.js``.

The upstream parser is built on the ``sax`` package configured with
``strict, xmlns, position`` but ``normalize:false, trim:false, lowercase``.
This is a hand-rolled tolerant tokenizer reproducing the observable behavior
SVGO depends on:

* attribute values are preserved verbatim (whitespace is *not* normalized;
  the ``cleanupAttrs`` plugin is responsible for that),
* text is trimmed and dropped when empty, except inside "text" elements
  (``textElems``) where it is preserved,
* comments are trimmed,
* ``<!DOCTYPE>`` internal entity declarations are parsed and applied.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from .collections import textElems
from .xast import (
    Cdata,
    Comment,
    Doctype,
    Element,
    Instruction,
    Root,
    Text,
    XastParent,
)


class SvgoParserError(Exception):
    def __init__(self, message: str, line: int, column: int, source: str, file: Optional[str] = None):
        self.reason = message
        self.line = line
        self.column = column
        self.source = source
        self.file = file
        super().__init__(f"{file or '<input>'}:{line}:{column}: {message}")


_ENTITY_DECL = re.compile(r"<!ENTITY\s+(\S+)\s+(?:'([^']+)'|\"([^\"]+)\")\s*>")

# Named XML entities that are always available.
_BASE_ENTITIES = {
    "lt": "<",
    "gt": ">",
    "amp": "&",
    "apos": "'",
    "quot": '"',
}

_ATTR_RE = re.compile(
    r"""([^\s"'>/=]+)               # attribute name
        (?:\s*=\s*
            (?:"([^"]*)"|'([^']*)'|([^\s"'>`]+))
        )?""",
    re.VERBOSE,
)


def _decode_entities(text: str, entities: Dict[str, str]) -> str:
    if "&" not in text:
        return text

    def repl(match: "re.Match[str]") -> str:
        body = match.group(1)
        if body.startswith("#x") or body.startswith("#X"):
            try:
                return chr(int(body[2:], 16))
            except ValueError:
                return match.group(0)
        if body.startswith("#"):
            try:
                return chr(int(body[1:], 10))
            except ValueError:
                return match.group(0)
        if body in entities:
            return entities[body]
        return match.group(0)

    return re.sub(r"&([^;]+);", repl, text)


def parse_svg(data: str, from_: Optional[str] = None) -> Root:
    root = Root()
    current: XastParent = root
    stack: List[XastParent] = [root]
    entities: Dict[str, str] = dict(_BASE_ENTITIES)

    def push(node) -> None:
        current.children.append(node)

    i = 0
    n = len(data)

    def _pos(idx: int):
        line = data.count("\n", 0, idx) + 1
        col = idx - (data.rfind("\n", 0, idx))
        return line, col

    while i < n:
        lt = data.find("<", i)
        if lt == -1:
            # trailing text
            _emit_text(data[i:], current, entities, push)
            break

        if lt > i:
            _emit_text(data[i:lt], current, entities, push)

        # markup constructs
        if data.startswith("<!--", lt):
            end = data.find("-->", lt + 4)
            if end == -1:
                raise SvgoParserError("Unterminated comment", *_pos(lt), data, from_)
            push(Comment(data[lt + 4 : end].strip()))
            i = end + 3
        elif data.startswith("<![CDATA[", lt):
            end = data.find("]]>", lt + 9)
            if end == -1:
                raise SvgoParserError("Unterminated CDATA", *_pos(lt), data, from_)
            push(Cdata(data[lt + 9 : end]))
            i = end + 3
        elif data.startswith("<!DOCTYPE", lt) or data.startswith("<!doctype", lt):
            end = _find_doctype_end(data, lt)
            if end == -1:
                raise SvgoParserError("Unterminated doctype", *_pos(lt), data, from_)
            doctype_body = data[lt + 2 : end]  # without leading "<!" and trailing ">"
            # store just the part after "<!DOCTYPE" like SVGO (sax gives the
            # doctype text without the surrounding markup delimiters)
            inner = data[lt + len("<!DOCTYPE") : end]
            push(Doctype("svg", {"doctype": inner}))
            # parse internal entity declarations
            for m in _ENTITY_DECL.finditer(data, lt, end + 1):
                entities[m.group(1)] = m.group(2) if m.group(2) is not None else m.group(3)
            i = end + 1
        elif data.startswith("<?", lt):
            end = data.find("?>", lt + 2)
            if end == -1:
                raise SvgoParserError("Unterminated processing instruction", *_pos(lt), data, from_)
            body = data[lt + 2 : end]
            parts = body.split(None, 1)
            name = parts[0] if parts else ""
            value = parts[1] if len(parts) > 1 else ""
            push(Instruction(name, value))
            i = end + 2
        elif data.startswith("</", lt):
            end = data.find(">", lt + 2)
            if end == -1:
                raise SvgoParserError("Unterminated closing tag", *_pos(lt), data, from_)
            stack.pop()
            current = stack[-1]
            i = end + 1
        else:
            # opening (or self-closing) tag
            end = _find_tag_end(data, lt)
            if end == -1:
                raise SvgoParserError("Unterminated tag", *_pos(lt), data, from_)
            raw = data[lt + 1 : end]
            self_closing = raw.endswith("/")
            if self_closing:
                raw = raw[:-1]
            name_match = re.match(r"\s*([^\s/>]+)", raw)
            if name_match is None:
                raise SvgoParserError("Invalid tag", *_pos(lt), data, from_)
            name = name_match.group(1)
            attrs = _parse_attributes(raw[name_match.end() :], entities)
            element = Element(name, attrs, [])
            push(element)
            if not self_closing:
                current = element
                stack.append(element)
            i = end + 1

    return root


def _emit_text(text: str, current: XastParent, entities: Dict[str, str], push) -> None:
    if current.type != "element":
        # root-level whitespace/text: SVGO ignores text outside of elements
        return
    decoded = _decode_entities(text, entities)
    if current.name in textElems:
        push(Text(decoded))
    else:
        value = decoded.strip()
        if value != "":
            push(Text(value))


def _parse_attributes(text: str, entities: Dict[str, str]) -> Dict[str, str]:
    attrs: Dict[str, str] = {}
    for m in _ATTR_RE.finditer(text):
        name = m.group(1)
        if name is None:
            continue
        value = m.group(2)
        if value is None:
            value = m.group(3)
        if value is None:
            value = m.group(4)
        if value is None:
            value = ""
        attrs[name] = _decode_entities(value, entities)
    return attrs


def _find_tag_end(data: str, start: int) -> int:
    """Find the ``>`` that closes a start tag, skipping quoted attribute values."""
    i = start + 1
    n = len(data)
    quote = ""
    while i < n:
        ch = data[i]
        if quote:
            if ch == quote:
                quote = ""
        elif ch in ('"', "'"):
            quote = ch
        elif ch == ">":
            return i
        i += 1
    return -1


def _find_doctype_end(data: str, start: int) -> int:
    """Find the ``>`` closing a DOCTYPE, accounting for an internal subset ``[...]``."""
    i = start
    n = len(data)
    depth = 0
    quote = ""
    while i < n:
        ch = data[i]
        if quote:
            if ch == quote:
                quote = ""
        elif ch in ('"', "'"):
            quote = ch
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        elif ch == ">" and depth <= 0:
            return i
        i += 1
    return -1
