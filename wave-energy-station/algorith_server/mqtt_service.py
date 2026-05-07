"""Shim: `from algorith_server.mqtt_service import` -> real module `alg.mqtt_service`."""
from alg.mqtt_service import *  # noqa: F401,F403
