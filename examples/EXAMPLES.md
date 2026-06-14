# Examples

Runnable examples that demonstrate how to use `modbus-config` as a library.
Each example is a self-contained `uv` project: it ships its own `pyproject.toml`
and can be run without activating any parent virtual environment.

| # | Directory | What it shows | Needs hardware? |
|---|-----------|---------------|-----------------|
| 1 | [`01_minimalmodbus/`](#1--read-named-registers-with-minimalmodbus) | Look up registers by name; apply FC, scale, enum | optional |
| 2 | [`02_codegen_jinja2/`](#2--generate-typed-getter-functions-with-jinja2) | Render a Python module of getter functions | no |
| 3 | [`03_mqtt_polling_plan/`](#3--build-a-modbusmqtt-polling-plan) | Build a JSON polling config for any MQTT bridge | no |
| 4 | [`04_advantech_csv/`](#4--generate-an-advantech-modbus-to-mqtt-csv-config) | Render a full Advantech RouterApp CSV mapping | no |
| 5 | [`05_generic_client_cli/`](#5--generic-modbus-tcp-client-and-cli) | Simplified dynamic client & Typer CLI using struct | optional |

---

## Quick start

```bash
# Clone and enter any example directory
git clone https://github.com/your-org/efoy-modbus-config
cd efoy-modbus-config/examples/01_minimalmodbus

# uv resolves dependencies (including local modbus-config & modbus-schema-common) automatically
uv run main.py
```

No `pip install`, no virtual environment activation required — `uv run` handles everything.

---

## 1 — Read named registers with MinimalModbus

**Directory:** `01_minimalmodbus/`  
**Dependencies:** `modbus-config`, `modbus-schema-common`, `minimalmodbus`

Looks up registers from the schema by name so you never hardcode addresses,
function codes, or scale factors in your application code.

```bash
# Demo mode (no hardware, default)
uv run main.py

# Real hardware (RS-485 serial)
uv run main.py --no-demo --port /dev/ttyUSB0 --slave 1 --baud 19200
```

**Key pattern:**
```python
spec = modbus_config.latest()
reg_map = {r.name: r for r in spec.registers}

_READ_FC = {
    ModbusRegisterType.INPUT_REGISTER:   4,
    ModbusRegisterType.HOLDING_REGISTER: 3,
    ModbusRegisterType.DISCRETE_INPUT:   2,
    ModbusRegisterType.COIL:             1,
}

def read_register(instrument, name: str):
    reg = reg_map[name]
    raw = instrument.read_register(reg.address_dec, functioncode=_READ_FC[reg.register_type])
    if getattr(reg, "enum_values", None):
        return reg.enum_values.get(str(raw), f"unknown ({raw})")
    return raw * getattr(reg, "scale_factor", 1.0)
```

> **Note:** MinimalModbus is a serial (RS-232/RS-485) library.
> For Modbus TCP use `pymodbus` with the same address/FC lookup pattern.

---

## 2 — Generate typed getter functions with Jinja2

**Directory:** `02_codegen_jinja2/`  
**Dependencies:** `modbus-config`, `modbus-schema-common`, `jinja2`

Uses the schema as a code-generation source. Renders a Python module with one
type-annotated getter function per register. The output has **zero runtime
dependency** on `modbus-config` — only `minimalmodbus` is needed.

```bash
# Print generated module to stdout
uv run main.py

# Write to file (input registers, default)
uv run main.py --out efoy_registers.py

# Generate getters for all register types
uv run main.py --type all --out efoy_all_registers.py

# Only holding registers
uv run main.py --type holding_register --out efoy_holding.py
```

**Example of generated output:**
```python
def read_SystemState(instrument: minimalmodbus.Instrument):
    """System operational state

    Address : 30040 (0x7568)
    FC      : 4
    Type    : uint16  RO
    """
    raw = instrument.read_register(30040, functioncode=4)
    _labels = {'0': 'off', '1': 'standby', '2': 'in operation', ...}
    return _labels.get(str(raw), f"unknown ({raw})")
```

Regenerate whenever you update the schema (new firmware → new PDF → new `vN.json`).

---

## 3 — Build a Modbus→MQTT polling plan

**Directory:** `03_mqtt_polling_plan/`  
**Dependencies:** `modbus-config`, `modbus-schema-common`

Constructs a complete JSON polling configuration from the latest schema.
A Modbus→MQTT bridge (Node-RED, Telegraf, a custom script) can consume
this at startup — no hand-maintained config files required.

```bash
# Preview first 5 entries on stderr, full JSON on stdout
uv run main.py

# Write full plan to file
uv run main.py --out plan.json

# Only read-only registers, custom topic prefix
uv run main.py --access RO --prefix factory/site1/efoy

# Omit write topics
uv run main.py --no-write-topics --out plan.json
```

**Example entry (RW holding register):**
```json
{
  "topic": "efoy/BatIdConfig",
  "subscribe_topic": "efoy/BatIdConfig/set",
  "address": 40001,
  "register_type": "holding_register",
  "read_fc": 3,
  "write_fc": 6,
  "register_count": 1,
  "data_type": "int16",
  "access": "RW",
  "scale": 1.0,
  "unit": null,
  "enum_values": null
}
```

---

## 4 — Generate an Advantech Modbus-to-MQTT CSV config

**Directory:** `04_advantech_csv/`  
**Dependencies:** `modbus-config`, `modbus-schema-common`, `jinja2`

Renders a complete CSV mapping file for the **Advantech RouterApp "Modbus to MQTT"
(APP-0087, firmware ≥ 6.4.x)**. Covers every readable and writable EFOY register.

The CSV uses 20 columns (A–T) matching the Advantech format:

| FC | Register type | Direction | Topic pattern |
|---|---|---|---|
| FC01 | `coil` | read | `{prefix}/{Name}` |
| FC02 | `discrete_input` | read | `{prefix}/{Name}` |
| FC03 | `holding_register` | read | `{prefix}/{Name}` |
| FC04 | `input_register` | read | `{prefix}/{Name}` |
| FC05/15 | `coil` | write | `{prefix}/{Name}/set` |
| FC06/16 | `holding_register` | write | `{prefix}/{Name}/set` |

Multi-word types (`float32`, `uint32`, `int32`) automatically get **Word** swap set.

```bash
# Print CSV to stdout (default IP/port/slave)
uv run main.py

# Write to file
uv run main.py --out efoy_mapping.csv

# Custom device parameters
uv run main.py --ip 10.0.0.50 --port 502 --slave 1 --prefix efoy --out efoy_mapping.csv

# 5 s polling, emit only on change, skip write rows
uv run main.py --poll 5000 --on-change --read-only --out efoy_readonly.csv

# PDU protocol addresses (subtract type offset: 30001, 40001, 10001)
uv run main.py --strip-prefix --out efoy_pdu.csv
```

**Example rows** (from `efoy_mapping.csv`):

```
# Read row — input register (FC04, RO)
efoy/SystemState,SystemState,192.168.1.100,502,1,4,30040,1,Unsigned Integer,None,FALSE,Unsigned Integer,1,0,10000,No,0,0,0,1

# Read row — discrete input (FC02, RO)
efoy/LogSystemOffOk,LogSystemOffOk,192.168.1.100,502,1,2,10001,1,Boolean,None,FALSE,Boolean,1,0,10000,No,0,0,0,1

# Read + write rows — holding register float32 (FC03 read / FC16 write, Word swap)
efoy/BatBocConfig,BatBocConfig,192.168.1.100,502,1,3,40003,2,Float,Word,FALSE,Float,1,0,10000,No,0,0,0,1
efoy/BatBocConfig/set,BatBocConfig,192.168.1.100,502,1,16,40003,2,Float,Word,FALSE,Float,1,0,10000,No,0,0,0,1

# Write-only coil (FC05, WO — no read row)
efoy/SystemOn/set,SystemOn,192.168.1.100,502,1,5,1,1,Boolean,None,FALSE,Boolean,1,0,10000,No,0,0,0,1
```

**Upload to the Advantech router:**
1. Run `uv run main.py --out efoy_mapping.csv` with your device's IP/port/slave ID.
2. Open the router web UI → Configuration → Global Settings.
3. Click **Upload CSV config file** and select `efoy_mapping.csv`.
4. A router restart may be required for the config to take effect.

### Data-type mapping

| EFOY `data_type` | Modbus data type | MQTT data type | Data swap | Words |
|---|---|---|---|---|
| `bit` | Boolean | Boolean | None | 1 bit |
| `uint16` | Unsigned Integer | Unsigned Integer | None | 1 |
| `int16` | Integer | Integer | None | 1 |
| `uint32` | Unsigned Integer | Unsigned Integer | Word | 2 |
| `int32` | Integer | Integer | Word | 2 |
| `float32` | Float | Float | Word | 2 |
| `string` | Unsigned Integer | String | None | N |

### Address convention

By default the script uses the `address_dec` values directly from the EFOY schema
(e.g. `30040` for `SystemState`). If your Advantech firmware requires PDU-level
addresses, pass `--strip-prefix` which subtracts the type offset:

| Register type | 5-digit base | Example schema addr | PDU addr (--strip-prefix) |
|---|---|---|---|
| `coil` | 00000 | 1 | 1 |
| `discrete_input` | 10000 | 10001 | 1 |
| `input_register` | 30000 | 30040 | 40 |
| `holding_register` | 40000 | 40001 | 1 |

---

## 5 — Generic Modbus TCP Client and CLI

**Directory:** `05_generic_client_cli/`  
**Dependencies:** `modbus-config`, `modbus-schema-common`, `pymodbus`, `typer`

Demonstrates how to build a fully generic Modbus TCP client and CLI tool that reads, writes, and decodes any register template dynamically using the schema registry. 

It maps registry data types (`float32`, `int16`, `bit`, `string`, etc.) using Python's built-in `struct` module for byte and word endianness translation.

```bash
# List all available registers in the latest schema
uv run main.py list

# Read a register value by name (with real-time decoding, scaling, and enum matching)
uv run main.py read SystemState --port 5025

# Write a value to a register by name (with real-time scaling and word encoding)
uv run main.py write BatIdConfig 2 --port 5025
```

**Key Pattern (Generic Decoders):**
```python
def decode_register(registers: list[int], reg: ModbusRegister, byte_order: str, word_order: str) -> any:
    # Uses python struct to decode registers matching reg.data_type, reg.byte_order, and reg.word_order
    # Apply scaling: val = val * reg.scale_factor
    # Apply enums: val = reg.enum_values[val]
    ...
```

---

## 6 — Generate Telegraf Modbus Config via Jinja2

**Directory:** `06_telegraf_input_plugin/`  
**Dependencies:** `modbus-config`, `modbus-schema-common`, `modbus-common`, `jinja2`

Generates a configuration file for the Telegraf `inputs.modbus` plugin. It reads a `devices.yaml` file to determine the target devices and which subset of registers to poll, resolving the data types and addresses from the central schema.

```bash
# Generate the config based on devices.yaml
uv run main.py --out telegraf.conf
```

### Docker Compose Test Setup

The example includes a `docker-compose.yml` defining a minimal test stack with Telegraf and InfluxDB. It is configured to run Telegraf on the host network to seamlessly poll the `modbus-simulator` running locally.

1. Start your modbus simulator:
```bash
uv run modbus-sim --port 5025
```

2. Generate the Telegraf config:
```bash
cd 06_telegraf_input_plugin
uv run main.py --out telegraf.conf
```

3. Start the test stack:
```bash
docker-compose up -d
```

4. Check Telegraf logs to see the data points (or log into InfluxDB at http://localhost:8086 with admin/adminpassword to view the data):
```bash
docker-compose logs -f telegraf
```
