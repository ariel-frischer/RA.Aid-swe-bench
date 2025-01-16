import logging
import sys

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
    if minimal:
        formatter = logging.Formatter('%(message)s')
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)

    return logger

class MinimalLogger:
    def __init__(self, base_logger):
        self._logger = base_logger
        self._minimal = False
        
    def setLevel(self, level):
        self._logger.setLevel(level)
        
    def set_minimal(self, minimal):
        self._minimal = minimal
        for handler in self._logger.handlers:
            if minimal:
                handler.setFormatter(logging.Formatter('%(message)s'))
            else:
                handler.setFormatter(logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                ))
    
    def debug(self, msg, *args, **kwargs):
        self._logger.debug(msg, *args, **kwargs)
        
    def info(self, msg, *args, **kwargs):
        self._logger.info(msg, *args, **kwargs)
        
    def warning(self, msg, *args, **kwargs):
        self._logger.warning(msg, *args, **kwargs)
        
    def error(self, msg, *args, **kwargs):
        self._logger.error(msg, *args, **kwargs)
        
    def critical(self, msg, *args, **kwargs):
        self._logger.critical(msg, *args, **kwargs)

# Create and configure the default logger instance
base_logger = setup_logger()
logger = MinimalLogger(base_logger)
