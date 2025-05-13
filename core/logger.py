# core/logger.py
import logging
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "logs"
LOG_PATH.mkdir(exist_ok=True)

LOG_FILE = LOG_PATH / "debug.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
