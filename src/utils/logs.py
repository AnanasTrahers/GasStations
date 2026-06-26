import functools
import inspect
import sys
import traceback
import logging

from src.utils.order import get_log_id

main_logger = logging.getLogger("MainLogger")
main_logger.setLevel(logging.DEBUG)
main_logger.propagate = False

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
)
ch.setFormatter(formatter)
main_logger.addHandler(ch)


logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)



def inject_traceback(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):

        f = sys._getframe(1 + kwargs.get("increase_depth", 0))
        loc, line = f.f_code.co_filename, f.f_lineno
        loc = loc[loc.find("src") :]
        func(*args, **kwargs, msg_location=(loc, line))

    return wrapper


class Logger:
    """
    basic wrapper around project logger
    use it for convenience
    """

    # @staticmethod
    # def _get_kyiv_time() -> str:
    #     tz_kyiv = ZoneInfo("Europe/Kyiv")
    #     return datetime.now(tz_kyiv).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def info(msg: str):
        main_logger.info(f"[{get_log_id()}] {msg}")

    @staticmethod
    def debug(msg: str):
        main_logger.debug(f"[{get_log_id()}] {msg}")

    @staticmethod
    def warning(msg: str):
        main_logger.warning(f"[{get_log_id()}] {msg}")

    @staticmethod
    @inject_traceback
    def error(msg: str, msg_location: tuple[str, int], *, increase_depth: int = 1):
        main_logger.error(f"[{get_log_id()}] {msg} | {msg_location} | {traceback.format_exc()}")


class LoggerMixin:
    @property
    def _log_prefix(self) -> str:
        class_name = self.__class__.__name__
        return f"[{class_name}]"

    @staticmethod
    def _get_caller_name() -> str:
        """Gets the name of the method that called the logger."""
        return f"[{inspect.stack()[2].function}]"

    def log_info(self, message: str):
        Logger.info(f"{self._log_prefix}{self._get_caller_name()} {message}")

    def log_warning(self, message: str):
        Logger.warning(f"{self._log_prefix}{self._get_caller_name()} {message}")

    def log_error(self, message: str):
        error_msg = f"{self._log_prefix}{self._get_caller_name()} ❌ ERROR: {message}"
        Logger.error(error_msg, increase_depth=2)
