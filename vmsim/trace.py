"""Memory reference traces: parsing and synthetic generation.

A trace is a list of ``(is_write, vaddr)`` tuples. The text format is one
reference per line::

    R 0x1000
    W 4096
    R 0x1004      # comments and blank lines ignored
"""

from __future__ import annotations

import random
from typing import Iterable

Reference = tuple[bool, int]


def parse_trace(lines: Iterable[str]) -> list[Reference]:
    out: list[Reference] = []
    for lineno, raw in enumerate(lines, 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            raise ValueError(f"line {lineno}: expected '<R|W> <addr>', got {raw!r}")
        op, addr = parts
        if op.upper() not in ("R", "W"):
            raise ValueError(f"line {lineno}: op must be R or W, got {op!r}")
        out.append((op.upper() == "W", int(addr, 0)))
    return out


def format_trace(refs: list[Reference]) -> str:
    return "\n".join(f"{'W' if w else 'R'} {addr:#x}" for w, addr in refs) + "\n"


# -- synthetic generators ------------------------------------------------
def sequential(n: int, page_size: int = 4096, start: int = 0,
               write_ratio: float = 0.0) -> list[Reference]:
    rng = random.Random(0)
    return [(rng.random() < write_ratio, start + i * (page_size // 4))
            for i in range(n)]


def uniform_random(n: int, span_pages: int = 256, page_size: int = 4096,
                   write_ratio: float = 0.3, seed: int = 0) -> list[Reference]:
    rng = random.Random(seed)
    return [(rng.random() < write_ratio,
             rng.randrange(span_pages) * page_size + rng.randrange(page_size))
            for _ in range(n)]


def working_set(n: int, hot_pages: int = 8, cold_pages: int = 200,
                hot_ratio: float = 0.9, page_size: int = 4096,
                write_ratio: float = 0.3, seed: int = 0,
                shift_every: int = 0) -> list[Reference]:
    """Locality model: most references hit a small 'hot' set that optionally
    drifts every ``shift_every`` references (models phase changes)."""
    rng = random.Random(seed)
    out: list[Reference] = []
    base = 0
    for i in range(n):
        if shift_every and i and i % shift_every == 0:
            base += hot_pages
        if rng.random() < hot_ratio:
            page = base + rng.randrange(hot_pages)
        else:
            page = hot_pages + rng.randrange(cold_pages)
        out.append((rng.random() < write_ratio,
                    page * page_size + rng.randrange(page_size)))
    return out


GENERATORS = {
    "sequential": sequential,
    "random": uniform_random,
    "working-set": working_set,
}
