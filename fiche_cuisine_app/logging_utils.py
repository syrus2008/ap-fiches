import logging
from typing import List, Optional
from datetime import datetime
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

class InMemoryLogHandler(logging.Handler):
    def __init__(self, capacity: int = 5000):
        super().__init__()
        self.capacity = capacity
        self.records: List[str] = []
        self.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s'))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.records.append(msg)
            # trim
            if len(self.records) > self.capacity:
                overflow = len(self.records) - self.capacity
                del self.records[0:overflow]
        except Exception:
            pass

    def get_text(self) -> str:
        return "\n".join(self.records)

    def clear(self):
        self.records.clear()

# Singleton-style accessor
_memory_handler: Optional[InMemoryLogHandler] = None
_file_handler_initialized: bool = False


def _get_default_log_path() -> str:
    # Prefer /app/logs in container; fallback to ./logs locally
    base = Path(os.environ.get("LOG_DIR", "/app/logs"))
    if not base.exists():
        base = Path("./logs")
        base.mkdir(parents=True, exist_ok=True)
    return str(base / "app.log")


def ensure_logging(level: int = logging.INFO) -> InMemoryLogHandler:
    global _memory_handler
    global _file_handler_initialized
    root = logging.getLogger()
    if not root.handlers:
        root.setLevel(level)
    else:
        root.setLevel(level)
    if _memory_handler is None:
        _memory_handler = InMemoryLogHandler()
        root.addHandler(_memory_handler)
    # File handler (rotating)
    if not _file_handler_initialized:
        log_file = os.environ.get("LOG_FILE", _get_default_log_path())
        try:
            fh = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
            fh.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s'))
            root.addHandler(fh)
            _file_handler_initialized = True
        except Exception:
            # Non-fatal: continue with in-memory only
            pass
    return _memory_handler


def get_logs_text() -> str:
    if _memory_handler is None:
        return ""
    return _memory_handler.get_text()


def clear_logs():
    if _memory_handler is not None:
        _memory_handler.clear()
