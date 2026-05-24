import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PDF_URL: str = os.getenv(
    "PDF_URL",
    "https://mev-energy.de/wp-content/uploads/250423_using-mobus-tcp.pdf",
)
PDF_LOCAL_PATH: Path = Path(os.getenv("PDF_LOCAL_PATH", "250423_using-mobus-tcp.pdf"))
DEVICE_NAME: str = os.getenv("DEVICE_NAME", "EFOY")
VERSION: str = os.getenv("VERSION", "1.0")

_output_path_env = os.getenv("OUTPUT_PATH")
OUTPUT_PATH: Path | None = Path(_output_path_env) if _output_path_env else None
