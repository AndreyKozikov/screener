import logging
from pathlib import Path
from datetime import datetime
from typing import Optional


def setup_data_update_logger(log_dir: Optional[Path] = None) -> logging.Logger:
    """
    Set up a logger for data update operations.
    
    Args:
        log_dir: Directory where log files should be stored. 
                If None, uses backend/logs directory.
    
    Returns:
        Configured logger instance.
    """
    if log_dir is None:
        # Default to backend/logs directory
        backend_dir = Path(__file__).parent.parent.parent
        log_dir = backend_dir / "logs"
    
    # Create log directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger("data_updates")
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create file handler with date-based filename
    log_file = log_dir / f"data_updates_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(file_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def get_data_update_logger() -> logging.Logger:
    """
    Get or create the data update logger.
    Creates logger on first call, reuses on subsequent calls.
    """
    logger = logging.getLogger("data_updates")
    
    # If logger doesn't have handlers, set it up
    if not logger.handlers:
        return setup_data_update_logger()
    
    return logger

