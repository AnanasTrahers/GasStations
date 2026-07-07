import functools
import inspect
import sys
import traceback
import logging
import structlog

from src.utils.order import get_log_id

handler = logging.StreamHandler(sys.stdout)

# --- Configure structlog ---
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="%H:%M:%S"),
        # structlog.stdlib.PositionalArgumentsFormatter(),
        # structlog.processors.StackInfoRenderer(),
        # structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(sort_keys=False),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

main_logger = structlog.get_logger("MainLogger")

logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


#
# main_logger = logging.getLogger("MainLogger")
# main_logger.setLevel(logging.DEBUG)
# main_logger.propagate = False
#
#
# ch = logging.StreamHandler()
# ch.setLevel(logging.DEBUG)
# formatter = logging.Formatter(
#     "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
# )
# ch.setFormatter(formatter)
# main_logger.addHandler(ch)
#
#
# logging.getLogger("uvicorn").setLevel(logging.WARNING)
# logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
# logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def inject_traceback(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        f = sys._getframe(1 + kwargs.get("increase_depth", 0))
        loc, line = f.f_code.co_filename, f.f_lineno
        loc = loc[loc.find("src"):]
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
    @inject_traceback
    def info(msg: str, *, msg_location: tuple[str, int], increase_depth: int = 0, event: str = "", **kwargs):
        main_logger.info(
            event + str(msg_location),
            log_id=get_log_id(),
            msg=msg,
            **kwargs
        )

    @staticmethod
    @inject_traceback
    def debug(msg: str, *, msg_location: tuple[str, int], increase_depth: int = 0, event: str = "", **kwargs):
        main_logger.debug(
            event + str(msg_location),
            log_id=get_log_id(),
            msg=msg,
            **kwargs
        )

    @staticmethod
    @inject_traceback
    def warning(msg: str, *, msg_location: tuple[str, int], increase_depth: int = 0, event: str = "", **kwargs):
        main_logger.warning(
            event + str(msg_location),
            log_id=get_log_id(),
            msg=msg,
            **kwargs
        )

    @staticmethod
    @inject_traceback
    def error(
            msg: str, *,
            error: Exception,
            msg_location: tuple[str, int],
            increase_depth: int = 0,
            event: str = "",
            **kwargs
    ):
        main_logger.error(
            event + str(msg_location),
            log_id=get_log_id(),
            msg=msg,
            error=error,
            **kwargs,
            traceback=traceback.format_exc(),
        )


class LoggerMixin:
    @property
    def _log_prefix(self) -> str:
        class_name = self.__class__.__name__
        return f"[{class_name}]"

    # @staticmethod
    # def _get_caller_name() -> str:
    #     """Gets the name of the method that called the logger."""
    #     return f"[{inspect.stack()[2].function}]"

    def log_info(self, msg: str, **kwargs):
        Logger.info(
            event=self._log_prefix,
            msg=msg,
            increase_depth=1,
            **kwargs
        )

    def log_warning(self, msg: str, **kwargs):
        Logger.warning(
            event=self._log_prefix,
            msg=msg,
            increase_depth=1,
            **kwargs
        )

    def log_error(self, msg: str, *, error: Exception, **kwargs):
        Logger.error(
            event=self._log_prefix,
            msg=msg,
            error=error,
            increase_depth=1,
            **kwargs
        )
