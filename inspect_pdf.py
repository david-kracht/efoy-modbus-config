"""
PDF structure inspector — run this to understand the raw table layout and
verify the parsed register output before running the full pipeline.

Usage:
    uv run python inspect_pdf.py
    uv run python inspect_pdf.py path/to/other.pdf
"""

import sys
from pathlib import Path

import pdfplumber

# Allow running without an editable install
sys.path.insert(0, str(Path(__file__).parent / "src"))


def inspect(pdf_path: Path) -> None:
    bar = "=" * 72
    thin = "-" * 72

    print(f"\n{bar}")
    print(f"  PDF: {pdf_path}")
    print(bar)

    with pdfplumber.open(pdf_path) as pdf:
        print(f"\n  Total pages: {len(pdf.pages)}\n")

        # ── Raw per-page view ─────────────────────────────────────────────
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

    # ── Parsed register entries ───────────────────────────────────────────
    print(f"\n{thin}")
    print("  PARSED REGISTER ENTRIES")
    print(f"  (register type inferred from address: 1xxxx=DI, 3xxxx=IR, 4xxxx=HR, <10000=Coil)")
    print(thin + "\n")

    from collections import Counter

    from efoy_modbus.extractor import extract_registers_raw
    from efoy_modbus.normalizer import raw_entry_to_register

    raw_entries = extract_registers_raw(pdf_path)
    registers = []
    skipped_raw = []
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

    print()
    print("  Sample registers (first 5 per type):")
    from efoy_modbus.models import ModbusRegisterType
    for rtype in ModbusRegisterType:
        subset = [r for r in registers if r.register_type == rtype][:5]
        if not subset:
            continue
        print(f"\n  [{rtype.value}]")
        for r in subset:
            print(f"    {r.address_dec:>6}  {r.name:<35} {r.data_type.value:<8}  {r.unit or ''}")

    if skipped_raw:
        print(f"\n  Skipped entries (name/address could not be parsed):")
        for e in skipped_raw[:10]:
            print(f"    {e}")


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("250423_using-mobus-tcp.pdf")
    if not path.exists():
        print(f"Error: PDF not found at {path!r}", file=sys.stderr)
        sys.exit(1)
    inspect(path)
