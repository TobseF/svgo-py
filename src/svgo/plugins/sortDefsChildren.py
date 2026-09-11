import functools

name = "sortDefsChildren"
description = "Sorts children of <defs> to improve compression"


def fn(root, params, info):
    def enter(node):
        if node.name != "defs":
            return
        frequencies = {}
        for child in node.children:
            if child.type == "element":
                frequencies[child.name] = frequencies.get(child.name, 0) + 1

        def cmp(a, b):
            if a.type != "element" or b.type != "element":
                return 0
            a_freq = frequencies.get(a.name)
            b_freq = frequencies.get(b.name)
            if a_freq is not None and b_freq is not None:
                fc = b_freq - a_freq
                if fc != 0:
                    return fc
            lc = len(b.name) - len(a.name)
            if lc != 0:
                return lc
            if a.name != b.name:
                return -1 if a.name > b.name else 1
            return 0

        node.children.sort(key=functools.cmp_to_key(cmp))

    return {"element": {"enter": lambda node, parent_node: enter(node)}}
