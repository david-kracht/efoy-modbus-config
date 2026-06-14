# Modbus Schema Generator

The `modbus-schema-generator` package is responsible for extracting Modbus specifications from external sources (e.g., PDFs or spreadsheets) and converting them into strict JSON schemas.

## Purpose

- Automates the tedious process of parsing manual spec sheets.
- Generates JSON definitions validated against `modbus-schema-common` models.
- Facilitates seamless updates to `modbus-config` when new firmware versions are released.
