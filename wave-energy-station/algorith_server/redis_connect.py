"""Shim: `from algorith_server.redis_connect import` -> real module `alg.redis_connect`."""
from alg.redis_connect import *  # noqa: F401,F403
