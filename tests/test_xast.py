"""Port of ``lib/xast.test.js`` (visitor behavior)."""

from svgo.visit import VISIT_SKIP, visit
from svgo.xast import Element, Root, detach_node_from_parent


def _x(name, children=None):
    return Element(name, {}, children or [])


def _root(children):
    return Root(children)


def test_visit_enters_nodes():
    ast = _root([_x("g", [_x("rect"), _x("circle")]), _x("ellipse")])
    entered = []
    visit(ast, {
        "root": {"enter": lambda node, parent: entered.append(node.type)},
        "element": {"enter": lambda node, parent: entered.append(f"{node.type}:{node.name}")},
    })
    assert entered == ["root", "element:g", "element:rect", "element:circle", "element:ellipse"]


def test_visit_exits_nodes():
    ast = _root([_x("g", [_x("rect"), _x("circle")]), _x("ellipse")])
    exited = []
    visit(ast, {
        "root": {"exit": lambda node, parent: exited.append(node.type)},
        "element": {"exit": lambda node, parent: exited.append(f"{node.type}:{node.name}")},
    })
    assert exited == ["element:rect", "element:circle", "element:g", "element:ellipse", "root"]


def test_visit_skips_children_when_detached():
    ast = _root([_x("g", [_x("rect"), _x("circle")]), _x("ellipse")])
    entered = []

    def enter(node, parent):
        entered.append(node.name)
        if node.name == "g":
            detach_node_from_parent(node, parent)

    visit(ast, {"element": {"enter": enter}})
    assert entered == ["g", "ellipse"]
    assert [c.name for c in ast.children] == ["ellipse"]


def test_visit_skips_children_on_symbol():
    ast = _root([_x("g", [_x("rect"), _x("circle")]), _x("ellipse")])
    entered = []

    def enter(node, parent):
        entered.append(node.name)
        if node.name == "g":
            return VISIT_SKIP

    visit(ast, {"element": {"enter": enter}})
    assert entered == ["g", "ellipse"]
    assert [c.name for c in ast.children] == ["g", "ellipse"]
