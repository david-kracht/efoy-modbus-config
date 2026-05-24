"""Example 2 — Generate typed getter functions with Jinja2
==========================================================
Uses the EFOY Modbus schema as a code-generation source.  Renders one
Python getter function per register.  The generated module has zero
dependency on efoy-modbus-config at runtime — only MinimalModbus is needed.

Usage:
    uv run main.py                                # print to stdout
    uv run main.py --out efoy_registers.py        # write to file
    uv run main.py --type input_register          # only input registers (default)
    uv run main.py --type all --out efoy_all.py   # all register types
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jinja2 import Environment, BaseLoader

import efoy_modbus
from efoy_modbus import ModbusRegisterType

from templates import _HEADER, _FUNC

# Standard Modbus function codes for reading
_READ_FC = {
    ModbusRegisterType.INPUT_REGISTER:   4,
    ModbusRegisterType.HOLDING_REGISTER: 3,
    ModbusRegisterType.DISCRETE_INPUT:   2,
    ModbusRegisterType.COIL:             1,
}

_ALL_TYPES = list(ModbusRegisterType)


def render(spec, filter_types: list[ModbusRegisterType]) -> str:
    env = Environment(loader=BaseLoader(), keep_trailing_newline=True)

    regs = [r for r in spec.registers if r.register_type in filter_types]
    reg_type_names = sorted({r.register_type.value for r in regs})

    header_tmpl = env.from_string(_HEADER)
    func_tmpl = env.from_string(_FUNC)

    parts = [header_tmpl.render(spec=spec, regs=regs, reg_types=reg_type_names)]

    for reg in regs:
        parts.append(func_tmpl.render(
            reg=reg,
            fc=_READ_FC[reg.register_type],
            unit=getattr(reg, "unit", None),
            scale=getattr(reg, "scale_factor", 1.0),
            enum_values=getattr(reg, "enum_values", None),
        ))

    return "".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MinimalModbus getter functions")
    parser.add_argument(
        "--type",
        choices=["input_register", "holding_register", "discrete_input", "coil", "all"],
        default="input_register",
        help="Register type(s) to generate (default: input_register)",
    )
    parser.add_argument("--out", help="Write output to this .py file (default: stdout)")
    args = parser.parse_args()

    spec = efoy_modbus.latest()

    if args.type == "all":
        filter_types = _ALL_TYPES
    else:
        filter_types = [ModbusRegisterType(args.type)]

    code = render(spec, filter_types)

    if args.out:
        Path(args.out).write_text(code, encoding="utf-8")
        line_count = code.count("\n")
        print(
            f"Written {line_count} lines / {len(code)} bytes to {args.out}",
            file=sys.stderr,
        )
    else:
        print(code)


if __name__ == "__main__":
    main()
