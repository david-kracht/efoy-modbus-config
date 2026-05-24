import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PDF_URL: str = os.getenv(
    "PDF_URL",
    "https://mev-energy.de/wp-content/uploads/250423_using-mobus-tcp.pdf",
)
PDF_LOCAL_PATH: Path = Path(os.getenv("PDF_LOCAL_PATH", "250423_using-mobus-tcp.pdf"))
OUTPUT_PATH: Path = Path(os.getenv("OUTPUT_PATH", "output/modbus_spec_v1.json"))
DEVICE_NAME: str = os.getenv("DEVICE_NAME", "EFOY")
VERSION: str = os.getenv("VERSION", "1.0")
