"""
EFOY Modbus Spec Pipeline

Usage:
    uv run python main.py                  # full pipeline -> output/modbus_spec_v1.json
    uv run python main.py --inspect        # inspection mode only (same as inspect_pdf.py)
    uv run python main.py --pdf path/to/file.pdf
    uv run python main.py --output path/to/out.json
"""

import argparse
import logging
import sys
from pathlib import Path

# Allow running without an editable install
sys.path.insert(0, str(Path(__file__).parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_inspect(pdf_path: Path) -> None:
    from inspect_pdf import inspect
    inspect(pdf_path)


def run_pipeline(pdf_path: Path, output_path: Path) -> None:
    from efoy_modbus.config import DEVICE_NAME, PDF_URL, VERSION
    from efoy_modbus.extractor import (
        extract_enum_type_definitions,
        extract_firmware_version,
        extract_registers_raw,
    )
    from efoy_modbus.models import ModbusInterfaceSpecification
    from efoy_modbus.normalizer import raw_entry_to_register

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

    # Log count per register type
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
    logger.info("Wrote %d registers + %d enum type definitions -> %s",
                len(registers), len(enum_defs), output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="EFOY Modbus Spec Pipeline")
    parser.add_argument("--inspect", action="store_true", help="Run inspection mode only")
    parser.add_argument("--pdf", type=Path, default=None, help="Override PDF source path")
    parser.add_argument("--output", type=Path, default=None, help="Override output JSON path")
    args = parser.parse_args()

    from efoy_modbus.config import OUTPUT_PATH, PDF_LOCAL_PATH, PDF_URL
    from efoy_modbus.downloader import resolve_pdf

    pdf_path = args.pdf or resolve_pdf(PDF_URL, PDF_LOCAL_PATH)

    if args.inspect:
        run_inspect(pdf_path)
    else:
        run_pipeline(pdf_path, args.output or OUTPUT_PATH)


if __name__ == "__main__":
    main()
