from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import modbus_config
from modbus_schema_common.resolver import resolve_schema
from modbus_schema_common.models import ModbusDataType, ModbusRegisterType
from modbus_common.config import AppConfig



def to_telegraf_type(data_type: ModbusDataType) -> str:
    mapping = {
        ModbusDataType.BIT: "BIT",
        ModbusDataType.UINT16: "UINT16",
        ModbusDataType.INT16: "INT16",
        ModbusDataType.UINT32: "UINT32",
        ModbusDataType.INT32: "INT32",
        ModbusDataType.FLOAT32: "FLOAT32",
        ModbusDataType.STRING: "STRING"
    }
    return mapping.get(data_type, "INT16")

def to_telegraf_register_type(reg_type: ModbusRegisterType) -> str:
    mapping = {
        ModbusRegisterType.COIL: "coil",
        ModbusRegisterType.DISCRETE_INPUT: "discrete",
        ModbusRegisterType.INPUT_REGISTER: "input",
        ModbusRegisterType.HOLDING_REGISTER: "holding"
    }
    return mapping.get(reg_type, "holding")

def to_telegraf_byte_order(byte_order: str, word_order: str) -> str:
    """
    Telegraf Byte Orders:
    ABCD -- Big Endian (Motorola)
    DCBA -- Little Endian (Intel)
    BADC -- Big Endian with byte swap
    CDAB -- Little Endian with byte swap
    """
    # EFOY defaults: byte_order = "big", word_order = "little" -> meaning BADC or CDAB?
    # Actually, EFOY schemas use: byte_order: "big", word_order: "little"
    # Wait, big endian bytes (AB), little endian words (CDAB) -> CDAB.
    # Let's map it simply:
    if byte_order == "big" and word_order == "little":
        return "CDAB" # Telegraf: Little Endian with byte swap
    elif byte_order == "big" and word_order == "big":
        return "ABCD"
    elif byte_order == "little" and word_order == "little":
        return "DCBA"
    elif byte_order == "little" and word_order == "big":
        return "BADC"
    return "ABCD"

def main():
    parser = argparse.ArgumentParser(description="Generate Telegraf modbus config from devices.yaml")
    parser.add_argument("--config", type=Path, default=Path("devices.yaml"), help="Path to devices.yaml")
    parser.add_argument("--out", type=Path, default=None, help="Output config file (default: stdout)")
    args = parser.parse_args()

    if not args.config.exists():
        print(f"Error: Config file {args.config} not found.", file=sys.stderr)
        sys.exit(1)

    app_config = AppConfig.load_from_yaml(args.config)
    
    template_data = []

    for device in app_config.devices:
        try:
            spec = resolve_schema(device.schema_name)
        except Exception as e:
            print(f"Error loading schema {device.schema_name} for device {device.name}: {e}", file=sys.stderr)
            continue

        # Map to telegraf format
        telegraf_byte_order = to_telegraf_byte_order(spec.byte_order.value, spec.word_order.value)
        
        # Group by register type
        groups = {}
        reg_dict = {r.name: r for r in spec.registers}
        
        # If specific registers are provided in the device config, use those. Otherwise, use all.
        regs_to_process = [reg_dict[r] for r in device.registers] if device.registers else spec.registers

        for reg in regs_to_process:
            t_reg_type = to_telegraf_register_type(reg.register_type)
            if t_reg_type not in groups:
                groups[t_reg_type] = []
                
            field = {
                "address": reg.protocol_address_dec,
                "name": reg.name,
                "type": to_telegraf_type(reg.data_type),
                "scale": getattr(reg, "scale_factor", None),
                "length": reg.register_count if reg.data_type == ModbusDataType.STRING else None
            }
            groups[t_reg_type].append(field)

        template_data.append({
            "name": device.name,
            "host": device.host,
            "port": device.port,
            "unit_id": device.unit_id,
            "byte_order": telegraf_byte_order,
            "groups": groups
        })

    env = Environment(loader=FileSystemLoader(Path(__file__).parent))
    template = env.get_template("telegraf.conf.jinja2")

    rendered = template.render(devices=template_data)

    if args.out:
        args.out.write_text(rendered, encoding="utf-8")
        print(f"Wrote config to {args.out}", file=sys.stderr)
    else:
        print(rendered)

if __name__ == "__main__":
    main()
