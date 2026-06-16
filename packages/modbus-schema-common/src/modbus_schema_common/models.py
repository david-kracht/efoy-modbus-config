from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ModbusRegisterType(str, Enum):
    DISCRETE_INPUT = "discrete_input"      # FC02 - 1-bit, read-only
    INPUT_REGISTER = "input_register"      # FC04 - 16-bit word, read-only
    COIL = "coil"                           # FC05 - 1-bit, write
    HOLDING_REGISTER = "holding_register"  # FC03 - 16-bit word, read/write


class ModbusDataType(str, Enum):
    UINT16 = "uint16"
    INT16 = "int16"
    UINT32 = "uint32"
    INT32 = "int32"
    FLOAT32 = "float32"
    STRING = "string"
    BIT = "bit"  # 1-bit value (Discrete Input / Coil), named per Modbus convention


class ModbusRegisterBase(BaseModel):
    """
    Base register — used for 1-bit registers (Discrete Input, Coil).
    No physical unit applies to bit-level values.
    """
    address_hex: str
    address_dec: int
    name: str                               # Original PascalCase name
    description: str
    data_type: ModbusDataType
    register_count: int
    access: Literal["RO", "RW", "WO"]
    register_type: ModbusRegisterType
    protocol_address_dec: Optional[int] = Field(default=None, exclude=True)  # Computed during load, not saved
    protocol_address_hex: Optional[str] = Field(default=None, exclude=True)  # Computed during load, not saved


class ModbusRegister(ModbusRegisterBase):
    """
    Word register — used for Input Register and Holding Register.
    Extends the base class with physical unit and optional enum value mapping.
    """
    unit: Optional[str] = None
    enum_values: Optional[dict[int, str]] = None  # set when type contains 'enum'


class EnumTypeDefinition(BaseModel):
    """
    Named enum type defined in spec sheets.
    """
    chapter: str            # e.g. "1.5", "1.7"
    name: str               # e.g. "SystemState", "BatteryType"
    values: dict[int, str]  # numeric code → human-readable label


class Endianness(str, Enum):
    BIG = "big"
    LITTLE = "little"


class ModbusInterfaceSpecification(BaseModel):
    device_name: str
    version: str
    source_url: Optional[str] = None        # URL the spec sheet was originally downloaded from
    firmware: Optional[str] = None          # firmware version extracted from the spec sheet
    byte_order: Endianness = Field(
        default=Endianness.BIG,
        description="Byte order within a 16-bit word (big = MSB first, little = LSB first)"
    )
    word_order: Endianness = Field(
        default=Endianness.LITTLE,
        description="Word order for multi-word values (big = MSW first, little = LSW first)"
    )
    address_mask: int = Field(
        default=10000,
        description=(
            "Decimal mask: protocol_addr = (schema_addr - 1) % address_mask. "
            "Strips the register-type prefix digit (e.g. 30001 → 0). "
            "0 = no masking, direct addressing (protocol_addr = schema_addr)."
        ),
    )
    # Union order matters for Pydantic v2 serialization: ModbusRegister (richer)
    # must be listed first so its extra fields are preserved.
    registers: list[ModbusRegister | ModbusRegisterBase] = Field(default_factory=list)
    enum_type_definitions: list[EnumTypeDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def compute_protocol_addresses(self) -> "ModbusInterfaceSpecification":
        m = self.address_mask
        for reg in self.registers:
            if reg.protocol_address_dec is None:
                addr = (reg.address_dec - 1) % m if m else reg.address_dec
                reg.protocol_address_dec = addr
                reg.protocol_address_hex = hex(addr)
        return self
