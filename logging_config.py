"""
Logging configuration for the Astronomy of the Day bot
Provides structured logging with different levels and file rotation
"""

import logging
import logging.handlers
import os
from datetime import datetime

def setup_logging(log_level=logging.INFO, log_to_file=True, log_to_console=True):
    """
    Set up comprehensive logging for the bot
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_to_file: Whether to log to file
        log_to_console: Whether to log to console
    """
    
    # Create logs directory if it doesn't exist
    if log_to_file and not os.path.exists("logs"):
        os.makedirs("logs")
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    handlers = []
    
    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)
    
    # File handlers
    if log_to_file:
        # Main log file with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            filename="logs/astronomy_bot.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
        
        # Error-only log file
        error_handler = logging.handlers.RotatingFileHandler(
            filename="logs/astronomy_bot_errors.log",
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        handlers.append(error_handler)
        
        # Daily log file
        daily_handler = logging.handlers.TimedRotatingFileHandler(
            filename="logs/astronomy_bot_daily.log",
            when='midnight',
            interval=1,
            backupCount=30,  # Keep 30 days
            encoding='utf-8'
        )
        daily_handler.setLevel(logging.INFO)
        daily_handler.setFormatter(formatter)
        handlers.append(daily_handler)
    
    # Add all handlers to root logger
    for handler in handlers:
        root_logger.addHandler(handler)
    
    # Log startup message
    logging.info("=== Logging System Initialized ===")
    logging.info(f"Log level: {logging.getLevelName(log_level)}")
    logging.info(f"Logging to file: {log_to_file}")
    logging.info(f"Logging to console: {log_to_console}")
    logging.info(f"Session started at: {datetime.now()}")

def log_system_info():
    """Log system information for debugging"""
    import platform
    import sys
    
    logger = logging.getLogger(__name__)
    
    logger.info("=== System Information ===")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {platform.platform()}")
    logger.info(f"Architecture: {platform.architecture()}")
    logger.info(f"Processor: {platform.processor()}")
    logger.info(f"Working directory: {os.getcwd()}")
    
def log_configuration_info():
    """Log configuration information"""
    logger = logging.getLogger(__name__)
    
    logger.info("=== Configuration Check ===")
    
    # Check environment variables (without revealing values)
    required_env_vars = [
        'CONSUMER_KEY', 'CONSUMER_SECRET', 'ACCESS_TOKEN', 
        'ACCESS_TOKEN_SECRET', 'BEARER_TOKEN', 'NASA_API_KEY', 'OPENAI_API_KEY'
    ]
    
    for var in required_env_vars:
        value = os.getenv(var)
        if value:
            logger.info(f"{var}: Configured ({'*' * min(len(value), 10)})")
        else:
            logger.warning(f"{var}: Not configured")

# Logging levels for different components
COMPONENT_LOG_LEVELS = {
    'tweepy': logging.WARNING,  # Reduce tweepy noise
    'urllib3': logging.WARNING,  # Reduce HTTP noise
    'requests': logging.WARNING,  # Reduce requests noise
    'openai': logging.INFO,      # Keep OpenAI logs
}

def set_component_log_levels():
    """Set specific log levels for different components"""
    for component, level in COMPONENT_LOG_LEVELS.items():
        logging.getLogger(component).setLevel(level)

def setup_bot_logging(debug_mode=False):
    """
    Convenience function to set up logging for the bot
    
    Args:
        debug_mode: If True, enables DEBUG level logging
    """
    log_level = logging.DEBUG if debug_mode else logging.INFO
    
    setup_logging(log_level=log_level)
    set_component_log_levels()
    log_system_info()
    log_configuration_info()
    
    return logging.getLogger("astronomy_bot")
