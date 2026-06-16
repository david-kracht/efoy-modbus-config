import re
from pathlib import Path
from typing import TypedDict

import pdfplumber


class RawRegisterEntry(TypedDict):
    name: str
    raw_type: str
    raw_address: str
    unit: str
    description: str
    is_enum: bool


# ---------------------------------------------------------------------------
# Column layout constants
# Each tuple: (name_c, type_c, addr_c, unit_c, desc_c)
# unit_c = -1 means no unit column for this layout.
# ---------------------------------------------------------------------------
_LAYOUT_5 = (0, 1, 3, 2, 4)   # name, type, addr, unit, desc
_LAYOUT_6 = (0, 1, 2, 3, 4)   # name, type, addr, unit, desc, _
_LAYOUT_12 = (1, 4, 7, -1, 10) # _, name, _, _, type, _, _, addr, _, _, desc, _
_LAYOUT_15 = (1, 4, 10, 7, 13) # _, name, _, _, type, _, _, unit, _, _, addr, _, _, desc, _

_TYPE_PREFIXES = (
    "float", "uint", "unit",  # 'unit32' is a PDF typo for 'uint32'
    "int", "bit", "bool", "str", "word", "real",
    "u16", "i16", "u32", "i32", "f32", "dword",
)

# ---------------------------------------------------------------------------
# Text-based fallback: register pattern in plain page text
# Format: RegisterName type[,] [enum] [unit] address description
# ---------------------------------------------------------------------------
_TYPE_KW = r'(?:float\s*32|uint32|uint16|int32|int16|unit32|bit|bool)'
_TEXT_REG_RE = re.compile(
    r'^([A-Z][A-Za-z0-9]+)'    # 1: name (must start with uppercase)
    r'\s+(' + _TYPE_KW + r')'  # 2: type keyword
    r',?'                       # optional trailing comma after type
    r'(?:\s+(enum))?'           # 3: optional "enum" qualifier (captured)
    r'(?:\s+([^\s\d,]+))?'     # 4: optional unit (single non-digit, non-space token)
    r'\s+(\d{1,6})'             # 5: address (Modbus range 1-65535)
    r'\s+(.+)$'                 # 6: description (rest of line)
)


def _looks_like_type(s: str) -> bool:
    cleaned = s.strip().lower().split("\n")[0].rstrip(",").strip()
    return any(cleaned.startswith(p) for p in _TYPE_PREFIXES)


def _clean(cell) -> str:
    return str(cell).strip() if cell is not None else ""


def _continuation_text(rows: list[list], col_idx: int) -> str:
    """Collect non-empty continuation text from rows[1:] at col_idx."""
    parts: list[str] = []
    for row in rows[1:]:
        if row and col_idx < len(row):
            val = _clean(row[col_idx])
            if val:
                parts.append(val)
    return " ".join(parts)


def _addr_to_dec(raw: str) -> int:
    """Convert a raw address string to int. Returns -1 on failure."""
    cleaned = raw.strip()
    hex_m = re.search(r'0[xX][0-9a-fA-F]+', cleaned)
    if hex_m:
        return int(hex_m.group(), 16)
    dec_m = re.search(r'^\d+$', cleaned)
    if dec_m:
        return int(cleaned)
    return -1


def _parse_table(raw_table: list[list]) -> RawRegisterEntry | None:
    """
    Parse a single raw pdfplumber table into a RawRegisterEntry.

    This PDF encodes each register as its own 1-to-N row table, where rows 2+
    are description continuation text. Six column layouts are observed:

        5-col : [name, type, unit, addr, desc]
        6-col : [name, type, addr, unit, desc, _]
        7A-col: [name, type, unit, addr, _, desc, _]   (col[1] looks like type)
        7B-col: [name, _, type, _, _, addr, desc]       (col[2] looks like type)
        9-col : [name, _, type, _, unit, addr, _, desc, _]
        12-col: [_, name, _, _, type, _, _, addr, _, _, desc, _]
        15-col: [_, name, _, _, type, _, _, unit, _, _, addr, _, _, desc, _]
    """
    if not raw_table or not raw_table[0]:
        return None

    first = [_clean(c) for c in raw_table[0]]
    ncols = len(first)

    if ncols == 5:
        name_c, type_c, addr_c, unit_c, desc_c = _LAYOUT_5
    elif ncols == 6:
        name_c, type_c, addr_c, unit_c, desc_c = _LAYOUT_6
    elif ncols == 12:
        name_c, type_c, addr_c, unit_c, desc_c = _LAYOUT_12
    elif ncols == 15:
        name_c, type_c, addr_c, unit_c, desc_c = _LAYOUT_15
    elif ncols == 7:
        if _looks_like_type(first[1]):
            # 7A: name[0], type[1], unit[2], addr[3], desc[5]
            name_c, type_c, addr_c, unit_c, desc_c = 0, 1, 3, 2, 5
        else:
            # 7B: name[0], type[2], addr[5], desc[6]
            name_c, type_c, addr_c, unit_c, desc_c = 0, 2, 5, -1, 6
    elif ncols == 9:
        # name[0], type[2], unit[4], addr[5], desc[7]
        name_c, type_c, addr_c, unit_c, desc_c = 0, 2, 5, 4, 7
    else:
        return None  # unknown layout

    name = first[name_c] if name_c < ncols else ""
    raw_type_full = first[type_c] if type_c < ncols else ""
    raw_address = first[addr_c] if addr_c < ncols else ""
    unit = first[unit_c] if unit_c >= 0 and unit_c < ncols else ""
    desc = first[desc_c] if desc_c < ncols else ""

    # Detect enum qualifier: may be in first row OR in a continuation row
    # of the type column (e.g. 9-col tables often put "enum" in row 1 col 2).
    is_enum = bool(re.search(r'\benum\b', raw_type_full, re.IGNORECASE))
    if not is_enum:
        for row in raw_table[1:]:
            if row and type_c < len(row) and row[type_c]:
                if re.search(r'\benum\b', str(row[type_c]), re.IGNORECASE):
                    is_enum = True
                    break

    # Strip newline + enum qualifier and trailing comma from type field
    raw_type = raw_type_full.split("\n")[0].rstrip(",").strip()

    # Append description continuation text from extra rows
    desc = (desc + " " + _continuation_text(raw_table, desc_c)).strip()

    if not name or not raw_address:
        return None  # skip continuation fragments and empty rows

    return RawRegisterEntry(
        name=name,
        raw_type=raw_type,
        raw_address=raw_address,
        unit=unit,
        description=desc,
        is_enum=is_enum,
    )


def _parse_text_entry(line: str) -> RawRegisterEntry | None:
    """
    Try to parse a register entry from a plain-text line.
    Used as fallback for registers that fall at page boundaries and are not
    captured as distinct pdfplumber tables.
    """
    m = _TEXT_REG_RE.match(line.strip())
    if not m:
        return None
    name, raw_type, enum_qualifier, unit, raw_address, description = m.groups()

    # Normalize "float 32" -> "float32" for consistency with table extraction
    raw_type = re.sub(r'\s+', '', raw_type)

    return RawRegisterEntry(
        name=name,
        raw_type=raw_type,
        raw_address=raw_address,
        unit=unit.strip() if unit else "",
        description=description.strip(),
        is_enum=bool(enum_qualifier),
    )


_SKIP_PATTERNS = [
    re.compile(r'^\s*\[?Point\]?|^\s*\[?\d+\]?\s*$'),  # page numbers like [5] or 5
    re.compile(r'SFC Energy AG', re.IGNORECASE),
    re.compile(r'Eugen-Sänger-Ring', re.IGNORECASE),
    re.compile(r'Brunnthal', re.IGNORECASE),
    re.compile(r'www\.sfc\.com', re.IGNORECASE),
    re.compile(r'Email:', re.IGNORECASE),
    re.compile(r'Modbus TCP\s*–\s*documentation', re.IGNORECASE),
    re.compile(r'System integration', re.IGNORECASE),
    re.compile(r'Vers\.\s*\d{2}/\d{4}', re.IGNORECASE),
    re.compile(r'^\s*Name\s+Type\s+Address\s+Description', re.IGNORECASE),
    re.compile(r'^\s*Name\s+Type\s+Unit\s+Address\s+Description', re.IGNORECASE),
]

_REGLINE_INDICATOR = re.compile(
    r'\b(?:float|uint\d+|int\d+|bit|bool|string|word|dword)\b|\b\d{5}\b',
    re.IGNORECASE
)

_SECTION_HEADER_RE = re.compile(r'^\s*\d{1,2}(?:\.\d{1,2})*\s+[A-Z]')
_COLUMN_HEADER_RE = re.compile(r'\bName\b.*\bType\b.*\bDesc', re.IGNORECASE)
_ENUM_HEADERS = [
    re.compile(r'SystemState\s+Operating\s*Mode', re.IGNORECASE),
    re.compile(r'System(?:On|Off)\s+Reason', re.IGNORECASE),
    re.compile(r'Battery\s+types', re.IGNORECASE),
    re.compile(r'Cartridge\s+types', re.IGNORECASE),
]


def _should_skip_continuation(line: str) -> bool:
    cleaned = line.strip()
    if not cleaned:
        return True
    for pat in _SKIP_PATTERNS:
        if pat.search(cleaned):
            return True
    return False


def extract_registers_raw(pdf_path: Path) -> list[RawRegisterEntry]:
    """
    Extract all register entries from the PDF.

    Strategy:
      1. Primary: parse each pdfplumber table (one table = one register in this PDF).
      2. Fallback: scan plain-text lines per page for register patterns that were
         missed due to page-boundary table splits.

    Deduplication is performed by decimal address to avoid double-counting entries
    that appear in both the table extraction and the page text.
    """
    table_entries: list[RawRegisterEntry] = []
    page_texts: list[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_texts.append(page.extract_text() or "")
            for raw_table in page.extract_tables():
                entry = _parse_table(raw_table)
                if entry is not None:
                    table_entries.append(entry)

    # Build seen-address set from table entries
    seen_addrs: set[int] = set()
    for e in table_entries:
        addr = _addr_to_dec(e["raw_address"])
        if addr >= 0:
            seen_addrs.add(addr)

    # Text-based fallback for registers missed by table extraction
    text_entries: list[RawRegisterEntry] = []
    last_entry: RawRegisterEntry | None = None
    for page_num, page_text in enumerate(page_texts):
        for line in page_text.splitlines():
            cleaned_line = line.strip()
            if not cleaned_line:
                continue

            # Check if this line is an enum definition header or similar to stop appending
            is_enum_header = False
            for pat in _ENUM_HEADERS:
                if pat.search(cleaned_line):
                    is_enum_header = True
                    break
            if is_enum_header:
                last_entry = None
                continue

            entry = _parse_text_entry(cleaned_line)
            if entry is not None:
                addr = _addr_to_dec(entry["raw_address"])
                if addr >= 0:
                    if addr not in seen_addrs:
                        text_entries.append(entry)
                        seen_addrs.add(addr)  # prevent duplicates across pages
                        last_entry = entry
                    else:
                        # Find the existing entry (from table_entries) and set last_entry to it
                        # so that we can append any cross-page continuation description lines!
                        existing = None
                        for te in table_entries:
                            if _addr_to_dec(te["raw_address"]) == addr:
                                existing = te
                                break
                        last_entry = existing
                else:
                    last_entry = None
            else:
                if last_entry is not None:
                    if _SECTION_HEADER_RE.search(cleaned_line) or _COLUMN_HEADER_RE.search(cleaned_line):
                        last_entry = None
                        continue

                    if _should_skip_continuation(cleaned_line):
                        continue

                    if _REGLINE_INDICATOR.search(cleaned_line):
                        last_entry = None
                        continue

                    # Process continuation line: check for "enum" keyword at start
                    enum_match = re.match(r'^\s*\benum\b\s*,?\s*(.*)$', cleaned_line, re.IGNORECASE)
                    if enum_match:
                        last_entry["is_enum"] = True
                        contrib = enum_match.group(1).strip()
                    else:
                        contrib = cleaned_line

                    if contrib:
                        # Prevent duplicate lines (if already captured by the table parser)
                        if contrib not in last_entry["description"]:
                            if last_entry["description"]:
                                last_entry["description"] += " " + contrib
                            else:
                                last_entry["description"] = contrib

    return table_entries + text_entries


# ---------------------------------------------------------------------------
# Enum type definition extraction (sections 1.5 – 1.8)
# These sections appear only as plain text; pdfplumber tables are empty there.
# ---------------------------------------------------------------------------

# Section 1.5: two-column side-by-side layout
# "SystemState Operating Mode" header, then rows like "0 off 0 Automatic"
_SYSSTATE_HEADER = re.compile(r'SystemState\s+Operating\s*Mode')
# Matches "0 off 0 Automatic" / "1 standby 1 off" — OperatingMode has only 0 and 1
_SYSSTATE_DOUBLE = re.compile(r'^(\d+)\s+(.*?)\s+(0|1)\s+([A-Za-z].+)$')
_SYSSTATE_SINGLE = re.compile(r'^(\d+)\s+(.+)$')

# Sections 1.6 – 1.8: "N: label" format
_REASON_HEADER = re.compile(r'(System(?:On|Off))\s+Reason')
_COLON_VAL = re.compile(r'^(\d+):\s*(.+)$')
# First value on the same header line: "Battery types 0: No Battery"
_BATTERY_FIRST = re.compile(r'Battery\s+types\s+(\d+):\s*(.+)')
_CARTRIDGE_FIRST = re.compile(r'Cartridge\s+types\s+(\d+):\s*(.+)')
# Page-marker pattern: "[27]" / "[27] any text" — structural, not content-specific
_PAGE_MARKER_RE = re.compile(r'^\[\d+\]')


def _is_enum_stop(line: str) -> bool:
    """True when a line should end enum-value continuation.

    Uses only structural signals — no footer-content matching:
      - section headers like "3 Serial…" or "2.4 Cartridge types"
      - PDF page-number markers: "[27]", "[28] …"
    """
    return bool(
        _SECTION_HEADER_RE.search(line) or _PAGE_MARKER_RE.match(line)
    )



# Pattern: "firmware 24.15.303" (case-insensitive)
_FIRMWARE_RE = re.compile(r'firmware\s+(\d+\.\d+\.\d+)', re.IGNORECASE)


def extract_firmware_version(pdf_path: Path) -> str | None:
    """
    Scan all pages of the PDF for the first occurrence of 'firmware X.Y.Z'
    and return the version string (e.g. '24.15.303'), or None if not found.
    """
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            m = _FIRMWARE_RE.search(text)
            if m:
                return m.group(1)
    return None


def extract_enum_type_definitions(pdf_path: Path) -> list:
    """
    Extract named enum type definitions from sections 1.5–1.8 of the PDF.

    Section 1.5 defines SystemState and OperatingMode as a two-column table
    that pdfplumber cannot read (rendered as an image-backed layout); values
    are parsed from the page plain-text instead.

    Sections 1.6–1.8 define SystemOnReason / SystemOffReason / BatteryType /
    CartridgeType using a "N: label" single-column format.

    Returns a list of EnumTypeDefinition objects (imported from models).
    """
    from modbus_schema_common.models import EnumTypeDefinition

    state_vals: dict[int, str] = {}
    mode_vals: dict[int, str] = {}
    on_vals: dict[int, str] = {}
    off_vals: dict[int, str] = {}
    bat_vals: dict[int, str] = {}
    cart_vals: dict[int, str] = {}

    section: str | None = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Reset last_key at every page boundary so footer text on one page
            # can never be appended to the last enum value of the previous page.
            last_key: int | None = None
            for raw_line in (page.extract_text() or "").splitlines():
                line = raw_line.strip()
                if not line:
                    continue

                # ── Section header detection ──

                if _SYSSTATE_HEADER.search(line):
                    section = "sysstate"
                    last_key = None
                    continue

                m = _BATTERY_FIRST.search(line)
                if m:
                    section = "battery"
                    last_key = int(m.group(1))
                    bat_vals[last_key] = m.group(2).strip()
                    continue

                m = _CARTRIDGE_FIRST.search(line)
                if m:
                    section = "cartridge"
                    last_key = int(m.group(1))
                    cart_vals[last_key] = m.group(2).strip()
                    continue

                m = _REASON_HEADER.search(line)
                if m:
                    section = "on_reason" if "On" in m.group(1) else "off_reason"
                    last_key = None
                    continue

                if section is None:
                    continue

                # ── Per-section value parsing ──

                if section == "sysstate":
                    m = _SYSSTATE_DOUBLE.match(line)
                    if m:
                        state_vals[int(m.group(1))] = m.group(2).strip()
                        mode_vals[int(m.group(3))] = m.group(4).strip()
                        continue
                    m = _SYSSTATE_SINGLE.match(line)
                    if m:
                        state_vals[int(m.group(1))] = m.group(2).strip()

                elif section in ("on_reason", "off_reason"):
                    m = _COLON_VAL.match(line)
                    if m:
                        target = on_vals if section == "on_reason" else off_vals
                        last_key = int(m.group(1))
                        target[last_key] = m.group(2).rstrip(".")
                    elif last_key is not None:
                        if _is_enum_stop(line):
                            last_key = None
                        else:
                            target = (
                                on_vals if section == "on_reason" else off_vals
                            )
                            if last_key in target:
                                target[last_key] = (
                                    target[last_key] + " " + line
                                ).rstrip(".")

                elif section in ("battery", "cartridge"):
                    m = _COLON_VAL.match(line)
                    if m:
                        target = bat_vals if section == "battery" else cart_vals
                        last_key = int(m.group(1))
                        target[last_key] = m.group(2).rstrip(".")
                    elif last_key is not None:
                        if _is_enum_stop(line):
                            last_key = None
                        else:
                            target = (
                                bat_vals if section == "battery" else cart_vals
                            )
                            if last_key in target:
                                target[last_key] = (
                                    target[last_key] + " " + line
                                ).rstrip(".")

    result: list[EnumTypeDefinition] = []
    if state_vals:
        result.append(EnumTypeDefinition(chapter="1.5", name="SystemState",     values=state_vals))
    if mode_vals:
        result.append(EnumTypeDefinition(chapter="1.5", name="OperatingMode",   values=mode_vals))
    if on_vals:
        result.append(EnumTypeDefinition(chapter="1.6", name="SystemOnReason",  values=on_vals))
    if off_vals:
        result.append(EnumTypeDefinition(chapter="1.6", name="SystemOffReason", values=off_vals))
    if bat_vals:
        result.append(EnumTypeDefinition(chapter="1.7", name="BatteryType",     values=bat_vals))
    if cart_vals:
        result.append(EnumTypeDefinition(chapter="1.8", name="CartridgeType",   values=cart_vals))
    return result
