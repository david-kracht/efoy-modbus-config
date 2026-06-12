"""
Command-line interface for the EFOY Modbus spec generation pipeline.

Registered as the ``efoy-generate`` console script in pyproject.toml.
Requires the ``[generate]`` optional dependencies::

    pip install efoy-modbus-config[generate]
    # or: uv sync --extra generate

Typical usage::

    # Generate next schema version automatically (e.g. v3.json when v2.json exists)
    efoy-generate --pdf 250423_using-mobus-tcp.pdf

    # Override output path explicitly
    efoy-generate --pdf new_spec.pdf --output /tmp/preview.json

    # Inspect raw pdfplumber tables (dev/debug)
    efoy-generate --inspect --pdf spec.pdf
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_GENERATE_DEPS = ("pdfplumber", "httpx", "dotenv")

# Try to resolve relative to workspace first (dev mode)
_workspace_schemas = None
for p in Path(__file__).resolve().parents:
    candidate = p / "packages/efoy-modbus/src/efoy_modbus/schemas"
    if candidate.exists():
        _workspace_schemas = candidate
        break

if _workspace_schemas:
    _SCHEMAS_DIR = _workspace_schemas
else:
    # Fallback to local schemas directory
    _SCHEMAS_DIR = Path.cwd() / "schemas"


def _check_generate_deps() -> None:
    """Exit with a helpful message if the [generate] extras are not installed."""
    missing = [pkg for pkg in _GENERATE_DEPS if not _try_import(pkg)]
    if missing:
        sys.exit(
            "The PDF generation pipeline requires additional dependencies.\n"
            "Install them with:\n\n"
            "    pip install efoy-modbus-config[generate]\n"
            "\nor, if using uv:\n\n"
            "    uv sync --extra generate\n"
        )


def _try_import(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _next_schema_path() -> Path:
    """
    Return the path for the next schema version.

    Scans *_SCHEMAS_DIR* for existing ``v*.json`` files, finds the highest N,
    and returns ``_SCHEMAS_DIR / 'v{N+1}.json'``.  Returns ``v1.json`` when no
    schemas exist yet.
    """
    existing = sorted(
        int(m.group(1))
        for f in _SCHEMAS_DIR.glob("v*.json")
        if (m := re.fullmatch(r"v(\d+)\.json", f.name))
    )
    next_n = (max(existing) + 1) if existing else 1
    return _SCHEMAS_DIR / f"v{next_n}.json"


# ---------------------------------------------------------------------------
# Inspect mode
# ---------------------------------------------------------------------------

def run_inspect(pdf_path: Path) -> None:
    import pdfplumber
    from collections import Counter

    from modbus_schema_generator.extractor import extract_registers_raw
    from modbus_schema_generator.normalizer import raw_entry_to_register

    bar = "=" * 72
    thin = "-" * 72

    print(f"\n{bar}")
    print(f"  PDF: {pdf_path}")
    print(bar)

    with pdfplumber.open(pdf_path) as pdf:
        print(f"\n  Total pages: {len(pdf.pages)}\n")

        print(thin)
        print("  RAW TABLES  (per page, as extracted by pdfplumber)")
        print(thin)

        raw_idx = 0
        for page_num, page in enumerate(pdf.pages, start=1):
            images = page.images
            tables = page.extract_tables()
            text_lines = (page.extract_text() or "").strip().splitlines()

            if not images and not tables and not text_lines:
                continue

            print(f"\n  [Page {page_num}]")
            if images:
                print(f"    ⚠  {len(images)} image(s) — possible image-encoded section heading")
            if text_lines:
                snippet = " | ".join(text_lines[:4])[:220]
                print(f"    Text: {snippet}")
            if not tables:
                print("    (no tables)")
                continue

            for tbl in tables:
                ncols = len(tbl[0]) if tbl else 0
                print(f"\n    ┌─ raw table [{raw_idx}]  rows={len(tbl)}  cols={ncols}")
                if tbl:
                    print(f"    │  row 0: {tbl[0]}")
                    for i, row in enumerate(tbl[1:3], start=1):
                        print(f"    │  row {i}: {row}")
                    if len(tbl) > 3:
                        print(f"    │  … ({len(tbl) - 1} continuation rows total)")
                raw_idx += 1

    print(f"\n{thin}")
    print("  PARSED REGISTER ENTRIES")
    print(f"  (type inferred from address: 1xxxx=DI  3xxxx=IR  4xxxx=HR  <10000=Coil)")
    print(thin + "\n")

    raw_entries = extract_registers_raw(pdf_path)
    registers, skipped_raw = [], []
    for entry in raw_entries:
        reg = raw_entry_to_register(entry)
        if reg is not None:
            registers.append(reg)
        else:
            skipped_raw.append(entry)

    counts = Counter(r.register_type.value for r in registers)
    print(f"  Total raw entries : {len(raw_entries)}")
    print(f"  Valid registers   : {len(registers)}")
    print(f"  Skipped entries   : {len(skipped_raw)}")
    print()
    for rtype, count in sorted(counts.items()):
        print(f"    {rtype:<25} {count}")

    print("\n  Sample registers (first 5 per type):")
    from modbus_schema_common.models import ModbusRegisterType
    for rtype in ModbusRegisterType:
        subset = [r for r in registers if r.register_type == rtype][:5]
        if not subset:
            continue
        print(f"\n  [{rtype.value}]")
        for r in subset:
            print(f"    {r.address_dec:>6}  {r.name:<35} {r.data_type.value:<8}  {r.unit or ''}")

    if skipped_raw:
        print("\n  Skipped entries (name/address could not be parsed):")
        for e in skipped_raw[:10]:
            print(f"    {e}")


# ---------------------------------------------------------------------------
# Generation pipeline
# ---------------------------------------------------------------------------

def run_pipeline(pdf_path: Path, output_path: Path) -> None:
    from modbus_schema_generator.config import DEVICE_NAME, PDF_URL, VERSION
    from modbus_schema_generator.extractor import (
        extract_enum_type_definitions,
        extract_firmware_version,
        extract_registers_raw,
    )
    from modbus_schema_common.models import ModbusInterfaceSpecification
    from modbus_schema_generator.normalizer import raw_entry_to_register

    firmware = extract_firmware_version(pdf_path)
    logger.info("Firmware version: %s", firmware or "(not found)")

    raw_entries = extract_registers_raw(pdf_path)
    logger.info("Extracted %d raw register entries from %s", len(raw_entries), pdf_path)

    enum_defs = extract_enum_type_definitions(pdf_path)
    logger.info("Extracted %d enum type definitions", len(enum_defs))
    for d in enum_defs:
        logger.info("  chapter %s  %-20s  %d values", d.chapter, d.name, len(d.values))

    definitions_by_name = {d.name: d for d in enum_defs}

    registers = []
    skipped = 0
    for entry in raw_entries:
        reg = raw_entry_to_register(entry, definitions_by_name)
        if reg is not None:
            registers.append(reg)
        else:
            skipped += 1

    registers.sort(key=lambda r: r.address_dec)
    logger.info("Parsed %d registers (%d entries skipped)", len(registers), skipped)

    from collections import Counter
    counts = Counter(r.register_type.value for r in registers)
    for rtype, count in sorted(counts.items()):
        logger.info("  %-20s %d", rtype, count)

    spec = ModbusInterfaceSpecification(
        device_name=DEVICE_NAME,
        version=VERSION,
        source_url=PDF_URL,
        firmware=firmware,
        registers=registers,
        enum_type_definitions=enum_defs,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
    logger.info(
        "Wrote %d registers + %d enum type definitions -> %s",
        len(registers), len(enum_defs), output_path,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    _check_generate_deps()

    default_output = _next_schema_path()

    parser = argparse.ArgumentParser(
        prog="efoy-generate",
        description=(
            "Generate the EFOY Modbus register specification JSON from the official PDF\n"
            "and write it directly into the package schemas directory.\n\n"
            f"Default output (auto-incremented version): {default_output}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--inspect", action="store_true",
        help="Print raw pdfplumber tables and parsed register summary (dev/debug)",
    )
    parser.add_argument("--pdf", type=Path, default=None, help="Override PDF source path")
    parser.add_argument(
        "--output", type=Path, default=None,
        help=(
            f"Override output path (default: {default_output.name} "
            "auto-determined from existing schemas)"
        ),
    )
    args = parser.parse_args()

    from modbus_schema_generator.config import OUTPUT_PATH as ENV_OUTPUT_PATH
    from modbus_schema_generator.config import PDF_LOCAL_PATH, PDF_URL
    from modbus_schema_generator.downloader import resolve_pdf

    pdf_path = args.pdf or resolve_pdf(PDF_URL, PDF_LOCAL_PATH)
    # Priority: 1) --output CLI arg  2) OUTPUT_PATH env var  3) auto-increment
    output_path = args.output or ENV_OUTPUT_PATH or default_output
    if ENV_OUTPUT_PATH and not args.output:
        logger.info("Using OUTPUT_PATH from environment: %s", ENV_OUTPUT_PATH)

    if args.inspect:
        run_inspect(pdf_path)
    else:
        logger.info("Output path: %s", output_path)
        run_pipeline(pdf_path, output_path)


if __name__ == "__main__":
    main()
