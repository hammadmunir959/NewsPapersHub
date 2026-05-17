import os
import sys
import logging
import logging.handlers
import structlog
from structlog.stdlib import BoundLogger

# Ensure the logs directory exists in the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
LOG_FILE_PATH = os.path.join(LOGS_DIR, "newspapershub.log")

def setup_logging() -> None:
    """
    Configures structlog to intercept and format both standard library logging
    and structured logging calls, sending output to stdout (console) and a timed
    rotating log file (last 3 days retained, daily rotation).
    """
    # 1. Shared processors for both stdout and file handlers
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # 2. Configure structlog wrapper
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 3. Formatter for beautiful console output
    console_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=True),
        ],
    )

    # 4. Formatter for structured JSON file output
    file_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    # 5. Define handlers
    # Console (Stdout) Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)

    # Timed Rotating File Handler (daily rotation, keeps last 3 days)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=LOG_FILE_PATH,
        when="D",
        interval=1,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)

    # 6. Hijack Root Logger
    root_logger = logging.getLogger()
    
    # Remove existing default handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)

    # Prevent verbosity in library logs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("whatsmeow").setLevel(logging.WARNING)

def get_logger(name: str) -> BoundLogger:
    """Return a configured structlog BoundLogger."""
    return structlog.get_logger(name)
