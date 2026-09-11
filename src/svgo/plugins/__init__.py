"""Built-in SVGO plugins, ported to Python.

Each plugin module exposes module-level ``name``, ``description`` and ``fn``.
``fn(root, params, info) -> visitor | None`` where ``visitor`` is a dict of
node-type -> {"enter": callable, "exit": callable}.
"""
