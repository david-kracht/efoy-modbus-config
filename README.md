# efoy-modbus-config

Python package that ships versioned Modbus register specifications for EFOY
fuel cells as structured, machine-readable data — and includes the deterministic
pipeline that generates them from the official firmware documentation PDF.

## Overview

EFOY fuel cells expose telemetry and control via Modbus TCP.  The register map
is published only as a PDF.  This project:

1. **Extracts** the complete register map from that PDF (pdfplumber pipeline)
2. **Validates** and normalises it into typed Pydantic models
3. **Ships the result as versioned package data** so any Python application can
   access it with a single import — no PDF, no manual parsing required

```
PDF (official spec)  →  efoy-generate  →  src/efoy_modbus/schemas/vN.json
                                                    ↓
                              pip install efoy-modbus-config
                                                    ↓
                              import efoy_modbus; spec = efoy_modbus.latest()
```

---

## Installation

### As a library (consumers)

```bash
pip install efoy-modbus-config
```

Only `pydantic` is required at runtime. No PDF tools, no network access.

### With the generation pipeline (maintainers / contributors)

```bash
pip install efoy-modbus-config[generate]
# or with uv:
uv sync --extra generate
```

---

## Using as a library

```python
import efoy_modbus

# List all bundled schema versions
efoy_modbus.versions()             # ['v1', 'v2']

# Load the latest schema
spec = efoy_modbus.latest()
print(spec.firmware)               # '24.15.303'
print(spec.device_name)            # 'EFOY'
print(len(spec.registers))         # 348

# Load a specific (older) version — int, bare string, and prefixed string all work
spec_v1 = efoy_modbus.load("v1")
spec_v1 = efoy_modbus.load(1)

# Iterate registers (sorted by address_dec ascending)
for reg in spec.registers:
    print(reg.name, reg.address_dec, reg.data_type, reg.access)

# Registers with enum state tables
for reg in spec.registers:
    if reg.enum_values:
        print(reg.name, reg.enum_values)

# Named enum type definitions (SystemState, BatteryType, …)
for enum_def in spec.enum_type_definitions:
    print(enum_def.chapter, enum_def.name, enum_def.values)
```

### Type annotations

All public models are re-exported from the top-level package:

```python
from efoy_modbus import (
    ModbusInterfaceSpecification,
    ModbusRegister,
    ModbusRegisterBase,
    ModbusDataType,
    ModbusRegisterType,
    EnumTypeDefinition,
)
```

---

## JSON schema

Each versioned file in `src/efoy_modbus/schemas/` contains a single object:

| Field | Type | Description |
|---|---|---|
| `device_name` | string | Device family name (default `"EFOY"`) |
| `version` | string | Spec schema version |
| `source_url` | string | URL the PDF was originally published at |
| `firmware` | string | Firmware version extracted from the PDF text |
| `registers` | array | All Modbus registers, sorted by `address_dec` |
| `enum_type_definitions` | array | Named enum types from sections 1.5–1.8 |

### Register object

```jsonc
{
  "address_hex": "0x752b",
  "address_dec": 30003,
  "name": "SystemState",         // PascalCase, from the PDF
  "description": "...",
  "data_type": "uint16",         // uint16 | int16 | uint32 | int32 | float32 | string | bit
  "register_count": 1,           // number of 16-bit registers occupied
  "access": "RO",                // RO | RW | WO
  "register_type": "input_register",  // coil | discrete_input | input_register | holding_register

  // word registers only (input_register / holding_register):
  "unit": "%",
  "scale_factor": 1.0,
  "enum_values": {               // present when the register encodes a named state
    "0": "off",
    "1": "standby",
    "2": "in operation"
  }
}
```

The current spec yields **348 registers**:

| Register type | Function code | Access | Count |
|---|---|---|---|
| `discrete_input` | FC02 | RO (1-bit) | 59 |
| `coil` | FC05 | WO (1-bit) | 34 |
| `input_register` | FC04 | RO (16-bit word) | 211 |
| `holding_register` | FC03 | RW (16-bit word) | 44 |

47 registers carry resolved `enum_values`; 6 named enum type definitions
(SystemState, OperatingMode, SystemOnReason, SystemOffReason, BatteryType,
CartridgeType) are available as top-level `enum_type_definitions`.

---

## Development setup

```bash
git clone https://github.com/your-org/efoy-modbus-config
cd efoy-modbus-config

# Create venv and install all dependencies including the PDF generation pipeline
uv sync --extra generate
```

uv creates `.venv/` automatically.  To run CLI commands you can either:

```bash
# Option A — activate once per shell session, then call the command directly
source .venv/bin/activate
efoy-generate --help

# Option B — prefix with 'uv run' (no activation needed, always works)
uv run efoy-generate --help
```

Place the official PDF (`250423_using-mobus-tcp.pdf`) in the project root, or
set `PDF_LOCAL_PATH` in `.env` to point to it.  If no local file is found, the
pipeline attempts to download it from `PDF_URL`.

```bash
# Copy and edit the environment file (optional — all settings have defaults)
cp .env.example .env
```

---

## Generating a new schema version

When a new firmware ships an updated PDF:

```bash
# Generate next schema version — auto-increments (v3 when v2 already exists)
efoy-generate --pdf new_spec.pdf

# Override output path explicitly if needed
efoy-generate --pdf new_spec.pdf --output /tmp/preview.json

# Debug: inspect raw pdfplumber tables and parsed register summary
efoy-generate --inspect --pdf new_spec.pdf

# Bump version in pyproject.toml, commit, tag, and publish
uv build
uv publish
```

The CLI writes directly into `src/efoy_modbus/schemas/vN.json` — no intermediate
`output/` folder or manual sync step needed.  The registry auto-discovers all
`v*.json` files in that directory, so `efoy_modbus.versions()` and
`efoy_modbus.latest()` reflect the new schema immediately after reinstall.

### Environment variables (`.env`)

| Variable | Default | Description |
|---|---|---|
| `PDF_URL` | *(mev-energy.de URL)* | Remote URL to download the PDF from |
| `PDF_LOCAL_PATH` | `250423_using-mobus-tcp.pdf` | Local PDF path (takes priority over URL) |
| `DEVICE_NAME` | `EFOY` | `device_name` field in the output |
| `VERSION` | `1.0` | `version` field in the output |

---

## Examples

Four runnable examples are provided in the [`examples/`](examples/) directory.
Each is a self-contained `uv` project — no manual venv activation needed.

| # | What it shows |
|---|---------------|
| [`01_minimalmodbus/`](examples/01_minimalmodbus/) | Read registers by name; resolve FC, scale factor, enum labels |
| [`02_codegen_jinja2/`](examples/02_codegen_jinja2/) | Render a typed Python getter-function module from the schema |
| [`03_mqtt_polling_plan/`](examples/03_mqtt_polling_plan/) | Build a JSON polling config for any Modbus→MQTT bridge |
| [`04_advantech_csv/`](examples/04_advantech_csv/) | Generate a full Advantech RouterApp CSV mapping (APP-0087) |

```bash
cd examples/01_minimalmodbus && uv run main.py          # demo mode, no hardware needed
cd examples/04_advantech_csv && uv run main.py --ip 192.168.1.100 --out efoy.csv
```

See [examples/EXAMPLES.md](examples/EXAMPLES.md) for full documentation of all examples.

---

```bash
# Build wheel and sdist
uv build

# Verify wheel contains the schema files
unzip -l dist/*.whl | grep schemas

# Publish to PyPI (requires PYPI_TOKEN env var or ~/.pypirc)
uv publish
```

---

## Project structure

```
src/efoy_modbus/
    __init__.py                 # Public API: load, latest, versions, models
    registry.py                 # Schema registry with lazy loading and caching
    schemas/
        __init__.py
        v1.json                 # Bundled schema snapshots (git-tracked)
        v2.json
    _cli.py                     # efoy-generate entry point (inspect + generate)
    config.py                   # Settings (env vars / defaults)
    downloader.py               # PDF download with local-file-first fallback
    extractor.py                # pdfplumber extraction + text fallback + enum defs
    normalizer.py               # RawRegisterEntry → Pydantic models
    models.py                   # Pydantic schema (ModbusInterfaceSpecification, …)
```

