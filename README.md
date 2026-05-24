# efoy-modbus-config

Deterministic pipeline that extracts the complete Modbus register specification
from the official EFOY fuel-cell documentation PDF and exports it as a
single, machine-readable JSON file — the **Single Source of Truth** for any
integration that talks Modbus TCP to an EFOY device.

## Purpose

EFOY fuel cells expose their telemetry and control interface over Modbus TCP.
The register map is published only as a PDF.  
This project automates the conversion:

```
PDF (official spec)  →  pipeline  →  output/modbus_spec_v1.json
```

The resulting JSON can be consumed directly by MQTT bridges, Home Assistant
integrations, SCADA systems, or any other tooling that needs to know which
register to read for, say, battery state-of-charge or operating mode.

## Output schema

`output/modbus_spec_v1.json` contains a single object:

| Field | Type | Description |
|---|---|---|
| `device_name` | string | Device family name (default `"EFOY"`) |
| `version` | string | Spec schema version |
| `source_url` | string | URL the PDF was originally published at |
| `firmware` | string | Firmware version extracted from the PDF text |
| `registers` | array | All Modbus registers (see below) |
| `enum_type_definitions` | array | Named enum types from sections 1.5–1.8 |

### Register object

Every entry in `registers` has:

```jsonc
{
  "address_hex": "0x752b",   // Modbus address as hex
  "address_dec": 30003,      // Modbus address as decimal
  "name": "SystemState",     // PascalCase name from the PDF
  "description": "...",
  "data_type": "uint16",     // uint16 | int16 | uint32 | int32 | float32 | string | bit
  "register_count": 1,       // number of 16-bit registers occupied
  "access": "RO",            // RO | RW | WO
  "register_type": "input_register",  // coil | discrete_input | input_register | holding_register

  // word registers only (input_register / holding_register):
  "unit": "%",               // physical unit, null if not applicable
  "scale_factor": 1.0,
  "enum_values": {           // present when the register encodes a named state
    "0": "off",
    "1": "standby",
    "2": "in operation"
  }
}
```

The current PDF yields **348 registers**:

| Register type | Function code | Access | Count |
|---|---|---|---|
| `discrete_input` | FC02 | RO (1-bit) | 59 |
| `coil` | FC05 | WO (1-bit) | 34 |
| `input_register` | FC04 | RO (16-bit word) | 211 |
| `holding_register` | FC03 | RW (16-bit word) | 44 |

47 registers carry resolved `enum_values`; 6 named enum type definitions
(SystemState, OperatingMode, SystemOnReason, SystemOffReason, BatteryType,
CartridgeType) are available as top-level `enum_type_definitions`.

## Requirements

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/) (recommended) **or** pip

## Setup

```bash
git clone https://github.com/your-org/efoy-modbus-config
cd efoy-modbus-config

# Install dependencies into an isolated venv
uv sync

# Copy and edit the environment file (optional — all settings have defaults)
cp .env.example .env
```

Place the official PDF (`250423_using-mobus-tcp.pdf`) in the project root, or
set `PDF_LOCAL_PATH` in `.env` to point to it.  
If no local file is found the pipeline will attempt to download it from
`PDF_URL`.

## Usage

```bash
# Run the full pipeline → output/modbus_spec_v1.json
uv run python main.py

# Override PDF source or output path
uv run python main.py --pdf /path/to/spec.pdf --output /path/to/out.json

# Inspect mode: print raw pdfplumber tables and extracted register summary
uv run python main.py --inspect
```

## Environment variables (`.env`)

| Variable | Default | Description |
|---|---|---|
| `PDF_URL` | *(mev-energy.de URL)* | Remote URL to download the PDF from |
| `PDF_LOCAL_PATH` | `250423_using-mobus-tcp.pdf` | Local PDF path (takes priority over URL) |
| `OUTPUT_PATH` | `output/modbus_spec_v1.json` | JSON output path |
| `DEVICE_NAME` | `EFOY` | `device_name` field in the output |
| `VERSION` | `1.0` | `version` field in the output |

## Project structure

```
main.py                   # CLI entry point
inspect_pdf.py            # diagnostic: raw table dump + register summary
src/efoy_modbus/
    config.py             # settings (env vars / defaults)
    downloader.py         # async PDF download with local-file-first fallback
    extractor.py          # pdfplumber extraction + text fallback + enum defs
    normalizer.py         # RawRegisterEntry → Pydantic models
    models.py             # Pydantic schema (ModbusInterfaceSpecification, …)
output/
    modbus_spec_v1.json   # generated output (not tracked in git)
```

## Regenerating the spec

Whenever a new firmware version ships with an updated PDF, replace the local
file and re-run the pipeline:

```bash
uv run python main.py
```

The `firmware` field in the output JSON is extracted automatically from the
PDF text (pattern `firmware X.Y.Z`) so the output always reflects the exact
specification version the PDF describes.
