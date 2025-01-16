import logging
import sys
from pathlib import Path

def setup_logger(log_level=logging.INFO):
    """Setup and configure the logger
    
    Args:
        log_level: Logging level to use (default: logging.INFO)
    
    Returns:
        Logger instance
    """
    logger = logging.getLogger("swe_lite_ra_aid")
    logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)

    return logger

# Create and configure the default logger instance
logger = setup_logger()
