"""Example 4 — Generate an Advantech Modbus-to-MQTT CSV configuration
======================================================================
Renders a complete CSV mapping file for the Advantech RouterApp
"Modbus to MQTT" (APP-0087, firmware ≥ 6.4.x) from the latest EFOY schema.

The CSV covers:
  • Every readable register  → read row  using FC 01/02/03/04
  • Every writable register  → write row using FC 05/06/15/16

Topic naming convention:
  • Read  : {prefix}/{RegisterName}
  • Write : {prefix}/{RegisterName}/set

Data-type mapping (EFOY schema → Advantech CSV):
  bit      → Boolean          (1 bit,   no swap)
  uint16   → Unsigned Integer (1 word,  no swap)
  int16    → Integer          (1 word,  no swap)
  uint32   → Unsigned Integer (2 words, Word swap)
  int32    → Integer          (2 words, Word swap)
  float32  → Float            (2 words, Word swap)
  string   → Unsigned Integer (N words, no swap — fallback; not natively supported)

Usage:
    uv run main.py                            # print CSV to stdout
    uv run main.py --out efoy_mapping.csv     # write to file

    uv run main.py --ip 10.0.0.50 --port 502 --slave 1 --prefix efoy
    uv run main.py --poll 5000 --on-change    # 5 s interval, emit only on change
    uv run main.py --read-only                # omit write rows

Address note:
    The address column uses the decimal values from the EFOY schema directly
    (e.g. 30003 for SystemState).  If your Advantech router app requires
    protocol-layer addresses (0-based), pass --strip-prefix to subtract the
    type offset (30001 for input registers, 40001 for holding registers, etc.).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

import efoy_modbus
from efoy_modbus import ModbusDataType, ModbusRegisterType

# ---------------------------------------------------------------------------
# Data-type mapping: EFOY schema → (Advantech modbus_dtype, mqtt_dtype, data_swap)
# ---------------------------------------------------------------------------
_DTYPE: dict[str, tuple[str, str, str]] = {
    ModbusDataType.BIT.value:     ("Boolean",         "Boolean",         "None"),
    ModbusDataType.UINT16.value:  ("Unsigned Integer", "Unsigned Integer", "None"),
    ModbusDataType.INT16.value:   ("Integer",          "Integer",          "None"),
    ModbusDataType.UINT32.value:  ("Unsigned Integer", "Unsigned Integer", "Word"),
    ModbusDataType.INT32.value:   ("Integer",          "Integer",          "Word"),
    ModbusDataType.FLOAT32.value: ("Float",            "Float",            "Word"),
    ModbusDataType.STRING.value:  ("Unsigned Integer", "String",           "None"),
}

# Read function codes per register type
_READ_FC = {
    ModbusRegisterType.COIL:             1,   # FC01 – read coils
    ModbusRegisterType.DISCRETE_INPUT:   2,   # FC02 – read discrete inputs
    ModbusRegisterType.HOLDING_REGISTER: 3,   # FC03 – read holding registers
    ModbusRegisterType.INPUT_REGISTER:   4,   # FC04 – read input registers
}

# Prefix offsets used when --strip-prefix is requested
_ADDR_OFFSET = {
    ModbusRegisterType.COIL:             0,       # coils:             00001 base
    ModbusRegisterType.DISCRETE_INPUT:   10000,   # discrete inputs:   10001 base
    ModbusRegisterType.INPUT_REGISTER:   30000,   # input registers:   30001 base
    ModbusRegisterType.HOLDING_REGISTER: 40000,   # holding registers: 40001 base
}


@dataclass
class CsvRow:
    topic: str
    name: str
    ip: str
    port: int
    device_id: int
    fc: int
    address: int
    data_length: int
    modbus_dtype: str
    data_swap: str
    byte_swap: str
    mqtt_dtype: str
    multiplier: str     # formatted as int when whole, float otherwise
    offset: int
    polling_ms: int
    send_when_change: str
    send_interval: int


def _format_multiplier(value: float) -> str:
    """Return '1' instead of '1.0' for whole-number scale factors."""
    if value == int(value):
        return str(int(value))
    return str(value)


def _data_length(reg) -> int:
    """Bits for 1-bit types; words (register_count) for word types."""
    if reg.register_type in (ModbusRegisterType.DISCRETE_INPUT, ModbusRegisterType.COIL):
        return 1
    return reg.register_count


def _write_fc(reg) -> Optional[int]:
    """Return the write FC, or None if the register type is not writable."""
    if reg.register_type == ModbusRegisterType.COIL:
        return 5 if reg.register_count == 1 else 15   # FC05 or FC15
    if reg.register_type == ModbusRegisterType.HOLDING_REGISTER:
        return 6 if reg.register_count == 1 else 16   # FC06 or FC16
    return None  # discrete_input and input_register are always read-only


def _make_row(
    reg,
    fc: int,
    topic: str,
    ip: str,
    port: int,
    device_id: int,
    address: int,
    polling_ms: int,
    send_when_change: str,
) -> CsvRow:
    modbus_dtype, mqtt_dtype, data_swap = _DTYPE.get(
        reg.data_type.value,
        ("Unsigned Integer", "Unsigned Integer", "None"),
    )
    scale = getattr(reg, "scale_factor", 1.0)
    return CsvRow(
        topic=topic,
        name=reg.name,
        ip=ip,
        port=port,
        device_id=device_id,
        fc=fc,
        address=address,
        data_length=_data_length(reg),
        modbus_dtype=modbus_dtype,
        data_swap=data_swap,
        byte_swap="FALSE",
        mqtt_dtype=mqtt_dtype,
        multiplier=_format_multiplier(scale),
        offset=0,
        polling_ms=polling_ms,
        send_when_change=send_when_change,
        send_interval=1,
    )


def build_rows(
    spec,
    *,
    ip: str,
    port: int,
    device_id: int,
    topic_prefix: str,
    polling_ms: int,
    send_on_change: bool,
    read_only: bool,
    strip_prefix: bool,
) -> list[CsvRow]:
    rows: list[CsvRow] = []
    soc = "Yes" if send_on_change else "No"

    for reg in spec.registers:
        addr = reg.address_dec
        if strip_prefix:
            addr = addr - _ADDR_OFFSET[reg.register_type]

        # Read row — all register types support a read function code
        if reg.access in ("RO", "RW"):
            rows.append(_make_row(
                reg,
                fc=_READ_FC[reg.register_type],
                topic=f"{topic_prefix}/{reg.name}",
                ip=ip, port=port, device_id=device_id, address=addr,
                polling_ms=polling_ms, send_when_change=soc,
            ))

        # Write row — coils and holding registers only
        if not read_only:
            wfc = _write_fc(reg)
            if wfc is not None and reg.access in ("RW", "WO"):
                rows.append(_make_row(
                    reg,
                    fc=wfc,
                    topic=f"{topic_prefix}/{reg.name}/set",
                    ip=ip, port=port, device_id=device_id, address=addr,
                    polling_ms=polling_ms, send_when_change=soc,
                ))

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Advantech Modbus-to-MQTT CSV from EFOY schema",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--ip",     default="192.168.1.100", help="Modbus device IP address")
    parser.add_argument("--port",   type=int, default=502,   help="Modbus TCP port")
    parser.add_argument("--slave",  type=int, default=1,     help="Modbus unit/slave ID")
    parser.add_argument("--prefix", default="efoy",          help="MQTT topic prefix")
    parser.add_argument("--poll",   type=int, default=10000, help="Polling interval in ms")
    parser.add_argument(
        "--on-change", action="store_true",
        help="Send only when value changes (default: always send)",
    )
    parser.add_argument(
        "--read-only", action="store_true",
        help="Omit write rows (FC05/06/15/16)",
    )
    parser.add_argument(
        "--strip-prefix", action="store_true",
        help="Convert 5-digit addresses to PDU addresses (subtract type offset)",
    )
    parser.add_argument("--out", help="Output CSV file path (default: stdout)")
    args = parser.parse_args()

    spec = efoy_modbus.latest()
    rows = build_rows(
        spec,
        ip=args.ip,
        port=args.port,
        device_id=args.slave,
        topic_prefix=args.prefix,
        polling_ms=args.poll,
        send_on_change=args.on_change,
        read_only=args.read_only,
        strip_prefix=args.strip_prefix,
    )

    read_rows  = sum(1 for r in rows if not r.topic.endswith("/set"))
    write_rows = sum(1 for r in rows if r.topic.endswith("/set"))
    print(
        f"Schema : {spec.device_name} {spec.version} (firmware {spec.firmware})\n"
        f"Rows   : {read_rows} read + {write_rows} write = {len(rows)} total",
        file=sys.stderr,
    )

    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    csv_content = env.get_template("mapping.csv.jinja2").render(rows=rows)

    if args.out:
        Path(args.out).write_text(csv_content, encoding="utf-8")
        print(f"Written to {args.out}", file=sys.stderr)
    else:
        print(csv_content)


if __name__ == "__main__":
    main()
