import re

from modbus_schema_generator.extractor import RawRegisterEntry
from modbus_schema_common.models import (
    EnumTypeDefinition,
    ModbusDataType,
    ModbusRegister,
    ModbusRegisterBase,
    ModbusRegisterType,
)

# ---------------------------------------------------------------------------
# Data type lookup
# ---------------------------------------------------------------------------

_DATA_TYPE_MAP: dict[str, ModbusDataType] = {
    "uint16": ModbusDataType.UINT16,
    "u16": ModbusDataType.UINT16,
    "unsignedint16": ModbusDataType.UINT16,
    "word": ModbusDataType.UINT16,
    "int16": ModbusDataType.INT16,
    "i16": ModbusDataType.INT16,
    "signedint16": ModbusDataType.INT16,
    "uint32": ModbusDataType.UINT32,
    "u32": ModbusDataType.UINT32,
    "unsignedint32": ModbusDataType.UINT32,
    "unit32": ModbusDataType.UINT32,   # typo in PDF
    "dword": ModbusDataType.UINT32,
    "int32": ModbusDataType.INT32,
    "i32": ModbusDataType.INT32,
    "signedint32": ModbusDataType.INT32,
    "float32": ModbusDataType.FLOAT32,
    "float": ModbusDataType.FLOAT32,
    "f32": ModbusDataType.FLOAT32,
    "real": ModbusDataType.FLOAT32,
    "string": ModbusDataType.STRING,
    "str": ModbusDataType.STRING,
    "bit": ModbusDataType.BIT,
    "bool": ModbusDataType.BIT,        # normalise legacy "bool" to BIT
    "boolean": ModbusDataType.BIT,
    "coil": ModbusDataType.BIT,
}

_REGISTER_COUNT: dict[ModbusDataType, int] = {
    ModbusDataType.UINT16: 1,
    ModbusDataType.INT16: 1,
    ModbusDataType.UINT32: 2,
    ModbusDataType.INT32: 2,
    ModbusDataType.FLOAT32: 2,
    ModbusDataType.STRING: 1,
    ModbusDataType.BIT: 1,
}

_ACCESS_BY_TYPE: dict[ModbusRegisterType, str] = {
    ModbusRegisterType.DISCRETE_INPUT: "RO",
    ModbusRegisterType.INPUT_REGISTER: "RO",
    ModbusRegisterType.HOLDING_REGISTER: "RW",
    ModbusRegisterType.COIL: "WO",
}

# Enum value pattern: "0 = Label text" (stops before next "N =" or end of string)
_ENUM_VAL_RE = re.compile(r'(\d+)\s*=\s*(.+?)(?=\s*\d+\s*=|\Z)', re.DOTALL)

# ---------------------------------------------------------------------------
# Field mappers
# ---------------------------------------------------------------------------


def map_data_type(raw: str) -> ModbusDataType:
    """Map a raw type string to a ModbusDataType, normalising whitespace/dashes."""
    cleaned = raw.strip().lower()
    cleaned = re.sub(r'[\s\-_]', '', cleaned)
    return _DATA_TYPE_MAP.get(cleaned, ModbusDataType.UINT16)


def parse_address(raw: str) -> tuple[str, int]:
    """Parse '0x0064', '100', or '100 (0x64)' -> (hex_str, dec_int)."""
    cleaned = raw.strip()
    hex_match = re.search(r'0[xX][0-9a-fA-F]+', cleaned)
    if hex_match:
        dec = int(hex_match.group(), 16)
        return hex_match.group().lower(), dec
    dec_match = re.search(r'\d+', cleaned)
    if dec_match:
        dec = int(dec_match.group())
        return hex(dec), dec
    return '0x0000', 0


def detect_register_type(address_dec: int) -> ModbusRegisterType:
    """
    Infer Modbus register type from the numeric address value:
      >= 40000 -> Holding Register  (FC03, R/W)
      >= 30000 -> Input Register    (FC04, R)
      >= 10000 -> Discrete Input    (FC02, R, 1-bit)
      <  10000 -> Coil              (FC05, W, 1-bit)
    """
    if address_dec >= 40000:
        return ModbusRegisterType.HOLDING_REGISTER
    if address_dec >= 30000:
        return ModbusRegisterType.INPUT_REGISTER
    if address_dec >= 10000:
        return ModbusRegisterType.DISCRETE_INPUT
    return ModbusRegisterType.COIL


def parse_enum_values(description: str) -> dict[int, str] | None:
    """
    Extract enum value definitions from a description string.

    Handles patterns like "0 = Not configured 1 = Custom 2 = Battery".
    Returns None when no enum definitions are found.
    """
    matches = _ENUM_VAL_RE.findall(description)
    if not matches:
        return None
    # Strip trailing punctuation that bleeds in from sentence-embedded enum lists
    return {int(k): re.sub(r'[,.)]+$', '', v).strip() for k, v in matches}


# ---------------------------------------------------------------------------
# Chapter-reference resolver for enum type definitions (sections 1.5–1.8)
# ---------------------------------------------------------------------------

_CHAPTER_REF_RE = re.compile(r'chapter\s+(1\.[5-8])', re.IGNORECASE)


def resolve_enum_ref(
    register_name: str,
    description: str,
    definitions: dict[str, EnumTypeDefinition],
) -> dict[int, str] | None:
    """
    Look up enum values for a register by resolving its 'see chapter 1.X'
    description reference against the extracted EnumTypeDefinition catalogue.

    Chapter 1.5 defines two enums: disambiguate by register name.
    Chapter 1.6 defines two enums: disambiguate by 'Off' in register name.
    Chapters 1.7 / 1.8 each define one enum.

    Falls back to name/keyword matching when the description is truncated and
    the chapter number is missing (page-boundary table splits in the PDF).
    """
    m = _CHAPTER_REF_RE.search(description)
    if m:
        chapter = m.group(1)
        if chapter == "1.5":
            key = "OperatingMode" if "OperatingMode" in register_name else "SystemState"
        elif chapter == "1.6":
            key = "SystemOffReason" if "Off" in register_name else "SystemOnReason"
        elif chapter == "1.7":
            key = "BatteryType"
        elif chapter == "1.8":
            key = "CartridgeType"
        else:
            return None
        defn = definitions.get(key)
        return dict(defn.values) if defn else None

    # Fallback: description is truncated before the chapter number — infer from
    # register name or description keywords.
    desc_lower = description.lower()
    if register_name in definitions:
        # e.g. "OperatingMode" register → OperatingMode definition
        return dict(definitions[register_name].values)
    if "cartridge" in desc_lower or "cartridge" in register_name.lower():
        defn = definitions.get("CartridgeType")
        return dict(defn.values) if defn else None
    if "battery" in desc_lower and "type" in desc_lower:
        defn = definitions.get("BatteryType")
        return dict(defn.values) if defn else None
    # Use PascalCase matching for On/Off to avoid "on" matching inside "reason"
    if "system" in register_name.lower() and "Off" in register_name:
        defn = definitions.get("SystemOffReason")
        return dict(defn.values) if defn else None
    if "system" in register_name.lower() and "On" in register_name:
        defn = definitions.get("SystemOnReason")
        return dict(defn.values) if defn else None
    if "SystemState" in register_name:
        defn = definitions.get("SystemState")
        return dict(defn.values) if defn else None
    return None


# ---------------------------------------------------------------------------
# Raw entry -> Pydantic model
# ---------------------------------------------------------------------------


def raw_entry_to_register(
    entry: RawRegisterEntry,
    definitions: dict[str, EnumTypeDefinition] | None = None,
) -> ModbusRegister | ModbusRegisterBase | None:
    """
    Convert a RawRegisterEntry into a Pydantic register model.

    - Returns ModbusRegister    for Input Register and Holding Register
      (word-level registers with unit metadata).
    - Returns ModbusRegisterBase for Discrete Input and Coil
      (bit-level registers without physical unit).
    - Returns None if the entry cannot be mapped to a valid register
      (missing name, unparseable address, or non-Modbus address range).
    """
    if not entry["name"] or not entry["raw_address"]:
        return None

    # Reject entries where raw_address is not a plain integer or hex literal
    if not re.fullmatch(r'\s*(?:0[xX][0-9a-fA-F]+|\d+)\s*', entry["raw_address"]):
        return None

    address_hex, address_dec = parse_address(entry["raw_address"])
    data_type = map_data_type(entry["raw_type"])
    register_type = detect_register_type(address_dec)

    # Parse enum values: inline first, then fall back to chapter reference lookup.
    # Note: is_enum may be False even for real enum registers when the "enum" keyword
    # appears on a continuation row that the table parser didn't capture — so we allow
    # resolve_enum_ref for any integer register when definitions are available.
    enum_values: dict[int, str] | None = None
    if entry["is_enum"]:
        enum_values = parse_enum_values(entry["description"])
    if enum_values is None and definitions and data_type in (
        ModbusDataType.UINT16,
        ModbusDataType.INT16,
        ModbusDataType.UINT32,
        ModbusDataType.INT32,
    ):
        enum_values = resolve_enum_ref(entry["name"], entry["description"], definitions)

    unit_raw = entry["unit"].strip() if entry["unit"] else ""

    common = dict(
        address_hex=address_hex,
        address_dec=address_dec,
        name=entry["name"],          # preserve original PascalCase from the PDF
        description=entry["description"],
        data_type=data_type,
        register_count=_REGISTER_COUNT[data_type],
        access=_ACCESS_BY_TYPE[register_type],
        register_type=register_type,
    )

    if register_type in (ModbusRegisterType.INPUT_REGISTER, ModbusRegisterType.HOLDING_REGISTER):
        return ModbusRegister(
            **common,
            unit=unit_raw if unit_raw else None,
            enum_values=enum_values,
        )

    return ModbusRegisterBase(**common)
