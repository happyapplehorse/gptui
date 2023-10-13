import logging


class NullHandler(logging.Handler):
    def emit(self, record):
        pass


def get_null_logger(name=None):
    logger = logging.getLogger(name or __name__)
    logger.addHandler(NullHandler())
    logger.propagate = False
    return logger
