# Modbus Schema Common

The `modbus-schema-common` package contains the fundamental Pydantic data models used across the Modbus configuration and control ecosystem.

## Purpose

- Defines `ModbusRegisterType`, `ModbusDataType`, and `ModbusRegisterBase`.
- Standardizes how registers, enum types, and overall `ModbusInterfaceSpecification`s are structured.
- Provides a centralized `registry` component to load and parse configuration schemas safely.
