"""
Shared configuration defaults for edgebox-gate product trees.

Each product keeps a local ``config`` module that extends :mod:`edgebox_config.base`
via star-import and applies small product-specific overrides. Runtime ``import config``
from within a product directory continues to resolve to that product\'s ``config.py``.
"""
