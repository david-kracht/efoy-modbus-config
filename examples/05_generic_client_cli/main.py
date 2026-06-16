"""Example 5 — Generic Modbus TCP Client and CLI
==============================================
Demonstrates how to build a fully generic Modbus TCP client and CLI tool
that reads, writes, and decodes any register template dynamically using the schema registry.

It uses python's built-in `struct` module for byte and word endianness translation,
and `pymodbus` for Modbus TCP socket communication.

Run help:
    uv run main.py --help

List registers:
    uv run main.py list

Read register (make sure a simulator or device is running):
    uv run main.py read SystemState --port 5025
"""

from __future__ import annotations

import struct
import typer
from pymodbus.client import ModbusTcpClient

import modbus_config
from modbus_schema_common import ModbusRegister, ModbusRegisterType, ModbusDataType




def decode_register(registers: list[int], reg: ModbusRegister, byte_order: str, word_order: str) -> any:
    """Decode raw 16-bit Modbus registers into Python types using struct and schema info."""
    fmt_map = {
        ModbusDataType.UINT16: "H",
        ModbusDataType.INT16: "h",
        ModbusDataType.UINT32: "I",
        ModbusDataType.INT32: "i",
        ModbusDataType.FLOAT32: "f",
        ModbusDataType.BIT: "H",
    }
    
    if reg.data_type == ModbusDataType.STRING:
        bo = ">" if byte_order == "big" else "<"
        raw_bytes = bytearray()
        for r in registers:
            raw_bytes.extend(struct.pack(f"{bo}H", r))
        return raw_bytes.decode("utf-8", errors="ignore").split("\x00")[0].strip()
        
    fmt_char = fmt_map.get(reg.data_type, "H")
    bo = ">" if byte_order == "big" else "<"
    
    if reg.register_count == 1:
        val_bytes = struct.pack(">H", registers[0])
        val = struct.unpack(f"{bo}{fmt_char}", val_bytes)[0]
        if reg.data_type == ModbusDataType.BIT:
            return bool(val)
        return val
        
    elif reg.register_count == 2:
        w0_bytes = struct.pack(">H", registers[0])
        w1_bytes = struct.pack(">H", registers[1])
        
        # Word order: big vs. little
        if word_order == "big":
            high_word_bytes = w0_bytes
            low_word_bytes = w1_bytes
        else:
            high_word_bytes = w1_bytes
            low_word_bytes = w0_bytes
            
        # Byte order: big vs. little
        if byte_order == "big":
            combined_bytes = high_word_bytes + low_word_bytes
        else:
            combined_bytes = low_word_bytes + high_word_bytes
            
        return struct.unpack(f"{bo}{fmt_char}", combined_bytes)[0]
    
    return registers[0] if len(registers) == 1 else registers


def encode_register(value: any, reg: ModbusRegister, byte_order: str, word_order: str) -> list[int]:
    """Encode python values into a list of 16-bit unsigned ints based on the schema."""
    fmt_map = {
        ModbusDataType.UINT16: "H",
        ModbusDataType.INT16: "h",
        ModbusDataType.UINT32: "I",
        ModbusDataType.INT32: "i",
        ModbusDataType.FLOAT32: "f",
    }
    
    if reg.data_type == ModbusDataType.STRING:
        text = str(value)
        byte_len = reg.register_count * 2
        padded = text.encode("utf-8", errors="ignore")[:byte_len].ljust(byte_len, b"\x00")
        bo = ">" if byte_order == "big" else "<"
        registers = []
        for i in range(0, byte_len, 2):
            registers.append(struct.unpack(f"{bo}H", padded[i:i+2])[0])
        return registers

    fmt_char = fmt_map.get(reg.data_type, "H")
    bo = ">" if byte_order == "big" else "<"
    
    if reg.register_count == 1:
        raw_val = int(value)
        val_bytes = struct.pack(f"{bo}{fmt_char}", raw_val)
        return [struct.unpack(">H", val_bytes)[0]]
        
    elif reg.register_count == 2:
        raw_val = float(value) if reg.data_type == ModbusDataType.FLOAT32 else int(value)
        combined_bytes = struct.pack(f"{bo}{fmt_char}", raw_val)
        
        partA = combined_bytes[0:2]
        partB = combined_bytes[2:4]
        
        if byte_order == "big":
            high_word_bytes = partA
            low_word_bytes = partB
        else:
            low_word_bytes = partA
            high_word_bytes = partB
            
        if word_order == "big":
            reg0 = struct.unpack(">H", high_word_bytes)[0]
            reg1 = struct.unpack(">H", low_word_bytes)[0]
        else:
            reg0 = struct.unpack(">H", low_word_bytes)[0]
            reg1 = struct.unpack(">H", high_word_bytes)[0]
            
        return [reg0, reg1]
        
    return []


class GenericModbusClient:
    """A fully generic Modbus TCP client wrapper.

    Translates all register transactions dynamically based on the schema metadata.
    """
    def __init__(self, host: str, port: int, unit_id: int, byte_order: str, word_order: str):
        self.client = ModbusTcpClient(host=host, port=port)
        self.unit_id = unit_id
        self.byte_order = byte_order
        self.word_order = word_order


    def connect(self) -> bool:
        return self.client.connect()

    def close(self) -> None:
        self.client.close()

    def read_register(self, reg: ModbusRegister) -> any:
        # 1. Fetch raw Modbus words based on register type (Function Code mapping)
        proto_addr = reg.protocol_address_dec
        if reg.register_type == ModbusRegisterType.INPUT_REGISTER:
            res = self.client.read_input_registers(proto_addr, count=reg.register_count, device_id=self.unit_id)
        elif reg.register_type == ModbusRegisterType.HOLDING_REGISTER:
            res = self.client.read_holding_registers(proto_addr, count=reg.register_count, device_id=self.unit_id)
        elif reg.register_type == ModbusRegisterType.COIL:
            res = self.client.read_coils(proto_addr, count=1, device_id=self.unit_id)
            if res.isError():
                raise IOError(f"Modbus error reading coil {reg.name}: {res}")
            return res.bits[0]
        elif reg.register_type == ModbusRegisterType.DISCRETE_INPUT:
            res = self.client.read_discrete_inputs(proto_addr, count=1, device_id=self.unit_id)
            if res.isError():
                raise IOError(f"Modbus error reading discrete input {reg.name}: {res}")
            return res.bits[0]
        else:
            raise ValueError(f"Unknown register type: {reg.register_type}")

        if res.isError():
            raise IOError(f"Modbus error reading {reg.name}: {res}")

        # 2. Decode raw payload
        val = decode_register(res.registers, reg, self.byte_order, self.word_order)
        
        # 3. Apply scaling factors
        scale = getattr(reg, "scale_factor", 1.0)
        if isinstance(val, (int, float)) and scale != 1.0:
            val = val * scale
            
        # 4. Translate enums to descriptive text
        if reg.enum_values and val is not None:
            try:
                int_key = int(val / scale) if scale != 1.0 else int(val)
                val = reg.enum_values.get(int_key, reg.enum_values.get(str(int_key), val))
            except (ValueError, TypeError):
                pass
                
        return val

    def write_register(self, reg: ModbusRegister, value: any) -> None:
        # 1. Parse discrete types directly
        proto_addr = reg.protocol_address_dec
        if reg.register_type == ModbusRegisterType.COIL:
            bool_val = str(value).lower() in ("true", "1", "yes")
            res = self.client.write_coil(proto_addr, bool_val, device_id=self.unit_id)
        elif reg.register_type == ModbusRegisterType.HOLDING_REGISTER:
            # 2. Encode structured data types (float32, etc.) into 16-bit words
            scale = getattr(reg, "scale_factor", 1.0)
            if scale != 1.0:
                raw_val = float(value) / scale
            else:
                raw_val = float(value) if reg.data_type == ModbusDataType.FLOAT32 else int(value)

            regs = encode_register(raw_val, reg, self.byte_order, self.word_order)
            if reg.register_count == 1:
                res = self.client.write_register(proto_addr, regs[0], device_id=self.unit_id)
            else:
                res = self.client.write_registers(proto_addr, regs, device_id=self.unit_id)
        else:
            raise ValueError(f"Register {reg.name} is not writable (type: {reg.register_type})")

        if res.isError():
            raise IOError(f"Modbus error writing to {reg.name}: {res}")


# ---------------------------------------------------------------------------
# Typer CLI Definition
# ---------------------------------------------------------------------------
app = typer.Typer(help="Simple, generic Modbus TCP CLI built from EFOY schemas")


@app.command("list")
def list_registers():
    """List all available registers defined in the latest schema."""
    spec = modbus_config.latest()
    typer.echo(f"Device Schema : {spec.device_name} (Firmware: {spec.firmware or 'N/A'})\n")
    typer.echo(f"{'Register Name':<30} | {'Addr (Dec)':<10} | {'Type':<18} | {'Access':<6}")
    typer.echo("-" * 72)
    for reg in spec.registers:
        typer.echo(f"{reg.name:<30} | {reg.address_dec:<10} | {reg.register_type.value:<18} | {reg.access:<6}")


@app.command("read")
def read_register(
    name: str = typer.Argument(..., help="Register name to read"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Modbus TCP host"),
    port: int = typer.Option(5025, "--port", "-p", help="Modbus TCP port"),
    unit_id: int = typer.Option(1, "--unit", "-u", help="Modbus slave unit ID"),
):
    """Read a register value by name, using dynamic schema settings."""
    spec = modbus_config.latest()
    reg = next((r for r in spec.registers if r.name == name), None)
    if not reg:
        typer.echo(f"Error: Register '{name}' not found in the latest schema.", err=True)
        raise typer.Exit(1)
        
    client = GenericModbusClient(host, port, unit_id, spec.byte_order.value, spec.word_order.value)
    if not client.connect():
        typer.echo(f"Error: Could not connect to Modbus TCP server at {host}:{port}.", err=True)
        raise typer.Exit(1)
        
    try:
        val = client.read_register(reg)
        unit = f" {reg.unit}" if reg.unit else ""
        typer.echo(f"{reg.name}: {val}{unit}")
    except Exception as e:
        typer.echo(f"Error reading register: {e}", err=True)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("write")
def write_register(
    name: str = typer.Argument(..., help="Register name to write to"),
    value: str = typer.Argument(..., help="Value to write (numeric or boolean string)"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Modbus TCP host"),
    port: int = typer.Option(5025, "--port", "-p", help="Modbus TCP port"),
    unit_id: int = typer.Option(1, "--unit", "-u", help="Modbus slave unit ID"),
):
    """Write a value to a register by name, using dynamic schema settings."""
    spec = modbus_config.latest()
    reg = next((r for r in spec.registers if r.name == name), None)
    if not reg:
        typer.echo(f"Error: Register '{name}' not found in the latest schema.", err=True)
        raise typer.Exit(1)
        
    client = GenericModbusClient(host, port, unit_id, spec.byte_order.value, spec.word_order.value)
    if not client.connect():
        typer.echo(f"Error: Could not connect to Modbus TCP server at {host}:{port}.", err=True)
        raise typer.Exit(1)
        
    try:
        client.write_register(reg, value)
        typer.echo(f"Success: Wrote value '{value}' to {reg.name}")
    except Exception as e:
        typer.echo(f"Error writing register: {e}", err=True)
        raise typer.Exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    app()
