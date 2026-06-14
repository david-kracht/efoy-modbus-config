import os
from dotenv import load_dotenv

load_dotenv()

SIM_HOST: str = os.getenv("SIM_HOST", "0.0.0.0")
SIM_PORT: int = int(os.getenv("SIM_PORT", "5025"))
SIM_SCHEMA: str = os.getenv("SIM_SCHEMA", "modbus_config/latest")
TITLE: str = os.getenv("SUITE_TITLE", "Modbus")
