import logging
import os
from logging.handlers import RotatingFileHandler


LOG_DIR_NAME = ".joint_space_visualizer"
LOG_FILE_NAME = "app.log"
ENV_LOG_DIR = "JSV_LOG_DIR"


def configure_logging():
    """Configure rotating file + console logging once and return log file path."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        handler = root_logger.handlers[0]
        if hasattr(handler, 'baseFilename'):
            return handler.baseFilename
        return None

    log_dir = os.environ.get(ENV_LOG_DIR)
    if not log_dir:
        log_dir = os.path.join(os.path.expanduser("~"), LOG_DIR_NAME)

    try:
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, LOG_FILE_NAME)
        file_handler = RotatingFileHandler(log_path, maxBytes=1_048_576, backupCount=3)
    except (PermissionError, OSError):
        fallback_dir = os.path.join(os.getcwd(), LOG_DIR_NAME)
        os.makedirs(fallback_dir, exist_ok=True)
        log_path = os.path.join(fallback_dir, LOG_FILE_NAME)
        file_handler = RotatingFileHandler(log_path, maxBytes=1_048_576, backupCount=3)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    root_logger.info("Logging initialized; writing to %s", log_path)
    return log_path
