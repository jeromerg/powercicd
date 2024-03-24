import logging
import functools


log = logging.getLogger(__name__)


# decorator to log entry and exit of a class method
call_depth = 0


def log_call():
    def log_call_decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            global call_depth
            prefix = "#" * call_depth
            non_self_args = args[1:]
            all_args_str = [str(arg) for arg in non_self_args] + [f"{key}={value}" for key, value in kwargs.items()]
            log.info(f"Entering {func.__name__}: {', '.join(all_args_str)}")
            call_depth += 1
            try:
                result = func(*args, **kwargs)
                log.info(f"Exiting {func.__name__}")
            except:
                log.exception(f"Exiting {func.__name__} with exception")
                raise
            finally:
                call_depth -= 1
            return result
        return wrapper
    return log_call_decorator
