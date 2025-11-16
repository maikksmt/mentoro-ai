# content/tests/utils.py
import contextlib
import logging


@contextlib.contextmanager
def silence_django_request_warnings():
    """
    Context manager that temporarily demotes django.request to ERROR
    and swaps handlers to silence noisy warnings during tests;
    restores original logger state on exit.
    """
    logger = logging.getLogger("django.request")
    old_level = logger.level
    old_propagate = logger.propagate
    old_handlers = list(logger.handlers)

    try:
        logger.setLevel(logging.ERROR)
        logger.propagate = False
        logger.handlers = [
            logging.NullHandler()
        ]
        yield
    finally:
        logger.handlers = old_handlers
        logger.propagate = old_propagate
        logger.setLevel(old_level)
