"""vmsim — a virtual-memory / demand-paging simulator."""

from .simulator import Stats, VirtualMemory, compare_policies
from .trace import parse_trace

__version__ = "0.1.0"
__all__ = ["VirtualMemory", "Stats", "compare_policies", "parse_trace"]
