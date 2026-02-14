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
    
    Notes:
        - Logger level: INFO (captures INFO, WARNING, ERROR, CRITICAL)
        - File handler level: INFO (все сообщения записываются в файл)
        - Console handler level: INFO (все сообщения выводятся в консоль)
        - Log rotation: daily (новый файл каждый день)
    """
    if log_dir is None:
        from config.paths import BACKEND_DIR
        log_dir = BACKEND_DIR / "logs"
    
    # Create log directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger("data_updates")
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create file handler with date-based filename
    # ИСПРАВЛЕНО: изменен уровень с WARNING на INFO для записи всех логов в файл
    log_file = log_dir / f"data_updates_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)  # Записываем INFO и выше в файл
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    
    # Console handler for INFO and above (shows data update progress in console)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
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

