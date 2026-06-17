import logging
import time
import functools
from datetime import datetime, timezone, timedelta

_BEIJING = timezone(timedelta(hours=8))


def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def retry(max_attempts: int = 3, delay: float = 2.0, exceptions=(Exception,)):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_attempts:
                        time.sleep(delay)
            raise last_exc

        return wrapper

    return decorator


def beijing_today() -> str:
    return datetime.now(_BEIJING).strftime("%Y-%m-%d")


def days_ago(n: int) -> str:
    return (datetime.now(_BEIJING) - timedelta(days=n)).strftime("%Y-%m-%d")
