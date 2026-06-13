"""Example 3 — Build a Modbus→MQTT polling plan
================================================
Constructs a complete polling configuration from the latest EFOY schema.
A Modbus→MQTT bridge (e.g. Node-RED, mqtt-modbus-bridge, or a custom script)
can consume this JSON at startup — no manually maintained config file needed.
Reinstall modbus-config when the firmware schema changes and re-run.

Usage:
    uv run main.py                      # preview first 5 entries on stderr + full JSON on stdout
    uv run main.py --out plan.json      # write full plan to file
    uv run main.py --access RO          # only read-only registers
    uv run main.py --prefix factory/efoy/cell1  # custom MQTT topic prefix
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import modbus_config
from modbus_schema_common import ModbusRegisterType

# Standard Modbus function codes
_READ_FC = {
    ModbusRegisterType.INPUT_REGISTER:   4,   # FC04 – read input registers
    ModbusRegisterType.HOLDING_REGISTER: 3,   # FC03 – read/write holding registers
    ModbusRegisterType.DISCRETE_INPUT:   2,   # FC02 – read discrete inputs (1-bit)
    ModbusRegisterType.COIL:             1,   # FC01 – read/write coils (1-bit)
}

_WRITE_FC = {
    ModbusRegisterType.HOLDING_REGISTER: 6,   # FC06 – write single holding register
    ModbusRegisterType.COIL:             5,   # FC05 – write single coil
}


def build_plan(
    spec,
    access_filter: tuple[str, ...],
    topic_prefix: str,
    include_write_topics: bool,
) -> list[dict]:
    plan = []
    for reg in spec.registers:
        if reg.access not in access_filter:
            continue

        entry = {
            "topic": f"{topic_prefix}/{reg.name}",
            "subscribe_topic": f"{topic_prefix}/{reg.name}/set" if include_write_topics else None,
            "address": reg.address_dec,
            "register_type": reg.register_type.value,
            "read_fc": _READ_FC[reg.register_type],
            "write_fc": _WRITE_FC.get(reg.register_type),   # None for RO types
            "register_count": reg.register_count,
            "data_type": reg.data_type.value,
            "access": reg.access,
            "scale": getattr(reg, "scale_factor", 1.0),
            "unit": getattr(reg, "unit", None),
            "enum_values": getattr(reg, "enum_values", None),
        }
        # Drop None write fields for read-only registers
        if entry["write_fc"] is None:
            del entry["subscribe_topic"]
            del entry["write_fc"]

        plan.append(entry)
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Build MQTT polling plan from EFOY schema")
    parser.add_argument(
        "--access",
        choices=["RO", "RW", "WO", "all"],
        default="all",
        help="Filter by register access mode (default: all)",
    )
    parser.add_argument("--prefix", default="efoy", help="MQTT topic prefix (default: efoy)")
    parser.add_argument(
        "--no-write-topics",
        action="store_true",
        help="Omit subscribe_topic / write_fc fields",
    )
    parser.add_argument("--out", help="Write JSON to this file (default: stdout)")
    parser.add_argument(
        "--preview",
        type=int,
        default=5,
        metavar="N",
        help="Print first N entries to stderr as a preview (default: 5)",
    )
    args = parser.parse_args()

    spec = modbus_config.latest()
    access_filter = ("RO", "RW", "WO") if args.access == "all" else (args.access,)

    plan = build_plan(
        spec,
        access_filter=access_filter,
        topic_prefix=args.prefix,
        include_write_topics=not args.no_write_topics,
    )

    # Print summary + preview to stderr so stdout stays clean for piping
    print(
        f"Schema : {spec.device_name} {spec.version} (firmware {spec.firmware})",
        file=sys.stderr,
    )
    print(f"Entries: {len(plan)}  (access filter: {args.access})", file=sys.stderr)
    if args.preview > 0:
        print(f"\nFirst {min(args.preview, len(plan))} entries:", file=sys.stderr)
        print(json.dumps(plan[: args.preview], indent=2), file=sys.stderr)

    payload = json.dumps(plan, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(f"\nFull plan written to {args.out}", file=sys.stderr)
    else:
        print(payload)


if __name__ == "__main__":
    main()
