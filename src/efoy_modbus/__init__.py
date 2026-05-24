"""
efoy-modbus-config — Versioned Modbus TCP register specification for EFOY fuel cells.

Provides machine-readable access to the EFOY Modbus register map, extracted
from the official firmware documentation and shipped as structured package data.

Quick start::

    import efoy_modbus

    # List all bundled schema versions
    efoy_modbus.versions()             # ['v1', 'v2']

    # Load the latest schema
    spec = efoy_modbus.latest()
    print(spec.firmware)               # '24.15.303'
    print(spec.device_name)            # 'EFOY'
    print(len(spec.registers))         # 348

    # Access register details
    for reg in spec.registers:
        print(reg.name, reg.address_dec, reg.data_type, reg.access)

    # Load a specific (older) version
    spec_v1 = efoy_modbus.load("v1")
    spec_v1 = efoy_modbus.load(1)      # int and bare string also accepted

    # Enum type definitions (SystemState, BatteryType, etc.)
    for enum_def in spec.enum_type_definitions:
        print(enum_def.name, enum_def.values)
"""

from efoy_modbus import registry
from efoy_modbus.models import (
    EnumTypeDefinition,
    ModbusDataType,
    ModbusInterfaceSpecification,
    ModbusRegister,
    ModbusRegisterBase,
    ModbusRegisterType,
)
from efoy_modbus.registry import latest, load, versions

__all__ = [
    # Registry API
    "load",
    "latest",
    "versions",
    "registry",
    # Pydantic models (for type annotations in downstream code)
    "ModbusInterfaceSpecification",
    "ModbusRegister",
    "ModbusRegisterBase",
    "ModbusDataType",
    "ModbusRegisterType",
    "EnumTypeDefinition",
]
