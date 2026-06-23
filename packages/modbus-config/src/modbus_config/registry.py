from __future__ import annotations
from modbus_schema_common.registry import register_package

_registry = register_package("modbus_config")

versions = _registry.versions
load = _registry.load
latest = _registry.latest
latest_version = _registry.latest_version
