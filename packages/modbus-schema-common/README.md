# Modbus Schema Common

The `modbus-schema-common` package contains the fundamental Pydantic data models used across the Modbus configuration and control ecosystem.

## Purpose

- Defines `ModbusRegisterType`, `ModbusDataType`, and `ModbusRegisterBase`.
- Standardizes how registers, enum types, and overall `ModbusInterfaceSpecification`s are structured.
- Provides a centralized `registry` component to load and parse configuration schemas safely.

## Architecture & Plugin System

The schema ecosystem uses a decoupled, dynamic "Drop-In" plugin architecture powered by Python Entry Points. 

### Schema Resolution

The Control Repository (e.g. `modbus-ctrl-center`, `modbus-sim`) is entirely decoupled from specific schema versions or file paths. It operates exclusively using abstract identifiers like `modbus_config/latest` or `device/v10`.

When an identifier is requested, the resolver within this package:
1. Parses the string into a package name (`modbus_config`) and a version (`latest`).
2. Accesses the internal `SchemaRegistry` to locate the JSON specification files for that package.
3. Automatically resolves `latest` to the highest available semantic version.
4. Parses and validates the JSON into a strongly typed Pydantic object (`ModbusInterfaceSpecification`) which is returned to the consuming application.

### Dynamic Discovery (Python Entry Points)

This package acts as a registry manager but **does not hardcode** any specific schema packages. Instead, it discovers them dynamically at runtime.

Any schema package (e.g. `modbus-config`, `device`) simply declares a Python Entry Point in its `pyproject.toml`:
```toml
[project.entry-points."modbus.schema"]
device = "device"
```

When `get_available_schemas()` is called, `importlib.metadata` scans the entire Python environment for packages claiming the `modbus.schema` group. 
Found plugins are imported on the fly, which triggers their `__init__.py` to call `register_package()`.

This creates a true **Drop-In** plugin system: Schema packages depend on `modbus-schema-common` to register themselves, but `modbus-schema-common` knows nothing about them.
