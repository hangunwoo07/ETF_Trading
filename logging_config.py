import logging
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path("logs")
GENERAL_LOG_FILE = LOG_DIR / "tradingbot.log"
ERROR_LOG_FILE = LOG_DIR / "tradingbot_error.log"
KST = timezone(timedelta(hours=9), "KST")


class KSTFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        record_time = datetime.fromtimestamp(record.created, tz=KST)
        if datefmt:
            return record_time.strftime(datefmt)
        return f"{record_time:%Y-%m-%d %H:%M:%S},{int(record.msecs):03d} GMT+9"


def setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)

    formatter = KSTFormatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        GENERAL_LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    error_file_handler = RotatingFileHandler(
        ERROR_LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_file_handler)
