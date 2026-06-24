import importlib.util

from apte.reporting.ascii import AsciiReporter

__all__ = ["AsciiReporter"]

if importlib.util.find_spec("rich"):
    from apte.reporting.rich_reporter import RichReporter

    __all__ += ["RichReporter"]
