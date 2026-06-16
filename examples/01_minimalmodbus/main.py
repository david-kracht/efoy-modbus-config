"""Example 1 — Read named registers with MinimalModbus
======================================================
Demonstrates how to use the modbus_config schema to look up register metadata
by name, so you never hardcode addresses, function codes, or scale factors.

Run in demo mode (no hardware needed, default):
    uv run main.py

Run against real hardware (RS-485 serial):
    uv run main.py --port /dev/ttyUSB0 --slave 1 --baud 19200

Note: MinimalModbus uses serial (RS-232/RS-485).  For Modbus TCP use pymodbus.
"""

from __future__ import annotations

import argparse

import modbus_config
from modbus_schema_common import ModbusRegisterType

# Standard Modbus function codes for reading
_READ_FC = {
    ModbusRegisterType.INPUT_REGISTER:   4,   # FC04 – read input registers (RO)
    ModbusRegisterType.HOLDING_REGISTER: 3,   # FC03 – read holding registers (RW)
    ModbusRegisterType.DISCRETE_INPUT:   2,   # FC02 – read discrete inputs (RO, 1-bit)
    ModbusRegisterType.COIL:             1,   # FC01 – read coils (RW, 1-bit)
}


def _proto(schema_addr: int, address_mask: int) -> int:
    """Convert 5-digit EFOY schema address to 0-based protocol address."""
    return (schema_addr - 1) % address_mask if address_mask else schema_addr


def read_register(instrument, reg_map: dict, name: str, address_mask: int):
    """Read a register by name and return a decoded Python value.

    Applies the scale factor and resolves enum labels automatically.
    """
    reg = reg_map[name]
    proto_addr = _proto(reg.address_dec, address_mask)
    raw = instrument.read_register(proto_addr, functioncode=_READ_FC[reg.register_type])
    enum_values = getattr(reg, "enum_values", None)
    scale_factor = getattr(reg, "scale_factor", 1.0)
    if enum_values:
        return enum_values.get(str(raw), f"unknown ({raw})")
    return raw * scale_factor


def write_holding_register(instrument, reg_map: dict, name: str, value: int, address_mask: int) -> None:
    """Write an integer value to a holding register (FC06)."""
    reg = reg_map[name]
    if reg.register_type != ModbusRegisterType.HOLDING_REGISTER:
        raise ValueError(f"{name} is not a holding register")
    proto_addr = _proto(reg.address_dec, address_mask)
    instrument.write_register(proto_addr, value, functioncode=6)


def main() -> None:
    parser = argparse.ArgumentParser(description="EFOY MinimalModbus example")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port")
    parser.add_argument("--slave", type=int, default=1, help="Modbus slave ID")
    parser.add_argument("--baud", type=int, default=19200, help="Baud rate")
    parser.add_argument("--demo", action="store_true", default=True,
                        help="Run with mock instrument (default: True)")
    parser.add_argument("--no-demo", dest="demo", action="store_false",
                        help="Connect to real hardware")
    args = parser.parse_args()

    spec = modbus_config.latest()
    reg_map = {r.name: r for r in spec.registers}

    print(f"Schema : {spec.device_name} — firmware {spec.firmware}")
    print(f"Registers: {len(spec.registers)}  |  versions: {modbus_config.versions()}\n")

    if args.demo:
        instrument = _MockInstrument()
        print("Running in demo mode — values are simulated\n")
    else:
        import minimalmodbus  # only needed when connecting to real hardware
        instrument = minimalmodbus.Instrument(args.port, slaveaddress=args.slave)
        instrument.serial.baudrate = args.baud

    registers_to_read = [
        "SystemState",     # input_register — enum (e.g. 'in operation')
        "BatBocStatus",    # input_register — battery state of charge status
        "AssemblyDate",    # input_register — string / multi-word
        "LogUBat",         # input_register — last battery voltage (V)
    ]

    print("Reading registers:")
    for name in registers_to_read:
        if name not in reg_map:
            print(f"  {name}: not found in schema (check schema version)")
            continue
        value = read_register(instrument, reg_map, name, spec.address_mask)
        reg = reg_map[name]
        unit = f" {reg.unit}" if getattr(reg, "unit", None) else ""
        fc = _READ_FC[reg.register_type]
        proto = _proto(reg.address_dec, spec.address_mask)
        print(f"  {name:30s}  schema={reg.address_dec}  proto={proto}  fc={fc}  → {value}{unit}")


class _MockInstrument:
    """Stand-in when no serial hardware is connected.

    Returns deterministic dummy values that exercise the decoding path
    (enum lookup, scale factor application) without requiring real hardware.
    """

    _CANNED = {
        # address_dec → raw integer value to return
        # Adjust to match specific test scenarios.
    }

    def read_register(self, address: int, functioncode: int = 3) -> int:
        if address in self._CANNED:
            return self._CANNED[address]
        # Default: return a small value derived from the address
        return address % 8


if __name__ == "__main__":
    main()
