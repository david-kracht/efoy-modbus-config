import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PKG_NAME: str = os.getenv("PKG_NAME", "modbus-config")
PDF_URL: str = os.getenv(
    "PDF_URL",
    "https://domain/YY_MM_Modbus_TCP.pdf",
)
PDF_LOCAL_PATH: Path = Path(os.getenv("PDF_LOCAL_PATH", "YY_MM_Modbus_TCP.pdf"))
DEVICE_NAME: str = os.getenv("DEVICE_NAME", "EFOY Fuel Cell")
VERSION: str = os.getenv("VERSION", "YY.MM")

_output_path_env = os.getenv("OUTPUT_PATH")
OUTPUT_PATH: Path | None = Path(_output_path_env) if _output_path_env else None
