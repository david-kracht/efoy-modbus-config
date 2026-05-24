from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


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
    No physical unit or scale factor applies to bit-level values.
    """
    address_hex: str
    address_dec: int
    name: str                               # Original PascalCase name from the PDF
    description: str
    data_type: ModbusDataType
    register_count: int
    access: Literal["RO", "RW", "WO"]
    register_type: ModbusRegisterType


class ModbusRegister(ModbusRegisterBase):
    """
    Word register — used for Input Register and Holding Register.
    Extends the base class with physical unit and scaling metadata.
    """
    unit: Optional[str] = None
    scale_factor: float = 1.0
    enum_values: Optional[dict[int, str]] = None  # set when type column contains 'enum'


class EnumTypeDefinition(BaseModel):
    """
    Named enum type defined in sections 1.5–1.8 of the PDF.
    Registers whose description references 'chapter 1.X' are linked at
    pipeline time by populating ModbusRegister.enum_values from here.
    """
    chapter: str            # e.g. "1.5", "1.7"
    name: str               # e.g. "SystemState", "BatteryType"
    values: dict[int, str]  # numeric code → human-readable label


class ModbusInterfaceSpecification(BaseModel):
    device_name: str
    version: str
    source_url: Optional[str] = None        # URL the PDF was originally downloaded from
    firmware: Optional[str] = None          # firmware version extracted from the PDF text
    # Union order matters for Pydantic v2 serialization: ModbusRegister (richer)
    # must be listed first so its extra fields are preserved.
    registers: list[ModbusRegister | ModbusRegisterBase] = Field(default_factory=list)
    enum_type_definitions: list[EnumTypeDefinition] = Field(default_factory=list)
