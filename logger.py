import logging
from functools import wraps
from collections import namedtuple

#===========FILTERS=============#

CondCountLog = namedtuple("Record", ["module", "level", "message", "cond_num"])


class NoRepeatedLogs(logging.Filter):
    """
    Logs only once: useful for checking how many conditionals are entered!

    Can also be used as a decorator to get a summary of conditionals hit.
    """
    def __init__(self, logger:logging.Logger=None, num_logged_ifs:int=None):
        super().__init__()
        self.logged_messages = set()
        self.found_ifs = []
        self.logger = logger
        self.num_logged_ifs = num_logged_ifs

    def filter(self, record):
        # add other fields if you need more granular comparison
        cond_num = getattr(record, 'cond_num', None)
        current_log = CondCountLog(module=record.module, level=record.levelno, message=record.msg, cond_num=cond_num)
        if current_log not in self.logged_messages and cond_num is not None:
            self.logged_messages.add(current_log)
            return True
        elif cond_num is None:
            #if there is cond num but it is in logged messages
            return True
        return False

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            self.logger.addFilter(self)
            
            # TODO: Does not work good if theres not if number...
            # logger_handler = logging.StreamHandler()  # Handler for the logger
            # self.logger.addHandler(logger_handler)
            # logger_handler.setFormatter(
            #     logging.Formatter('%(levelname)s / COND: %(cond_num)s')
            # )
            try:
                return func(*args, **kwargs)
            finally:
                self.logger.info("===========================SUMMARY============================")
                self.logger.info(f"HIT CONDITIONAL NUMBERS: {sorted(l.cond_num for l in self.logged_messages if l.cond_num is not None)}")
                self.logger.info(f"CONDITIONALS HIT SUMMARY: {len(self.logged_messages)}/{self.num_logged_ifs}")
                self.logger.info("=============================DONE=============================")
                self.logger.removeFilter(self)
        return wrapper