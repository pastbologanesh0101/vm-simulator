"""Page-replacement policies.

Each policy tracks the set of resident VPNs and picks a victim when a frame is
needed. The simulator calls:

* ``on_load(vpn)``   — a page was just paged in
* ``on_access(vpn, is_write)`` — a resident page was touched (hit)
* ``victim()``       — choose and forget a page to evict

``Optimal`` additionally needs to see the future, provided via ``set_future``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import OrderedDict, deque


class Policy(ABC):
    name = "base"

    @abstractmethod
    def on_load(self, vpn: int) -> None: ...

    def on_access(self, vpn: int, is_write: bool) -> None:  # noqa: D401
        """Default: hits don't change eviction order."""

    @abstractmethod
    def victim(self) -> int: ...

    # Only Optimal uses these; the simulator calls them on every policy.
    def set_vpn_trace(self, vpn_trace: list[int]) -> None:
        pass

    def tick(self, index: int) -> None:
        pass


class FIFO(Policy):
    name = "fifo"

    def __init__(self, capacity: int):
        self._q: deque[int] = deque()

    def on_load(self, vpn: int) -> None:
        self._q.append(vpn)

    def victim(self) -> int:
        return self._q.popleft()


class LRU(Policy):
    name = "lru"

    def __init__(self, capacity: int):
        self._order: OrderedDict[int, None] = OrderedDict()

    def on_load(self, vpn: int) -> None:
        self._order[vpn] = None
        self._order.move_to_end(vpn)

    def on_access(self, vpn: int, is_write: bool) -> None:
        self._order.move_to_end(vpn)

    def victim(self) -> int:
        vpn, _ = self._order.popitem(last=False)
        return vpn


class Clock(Policy):
    """Second-chance: a circular buffer of frames with a reference bit."""

    name = "clock"

    def __init__(self, capacity: int):
        self._slots: list[int] = []       # vpns in insertion order (the ring)
        self._ref: dict[int, bool] = {}
        self._hand = 0

    def on_load(self, vpn: int) -> None:
        self._slots.append(vpn)
        self._ref[vpn] = True             # loaded pages start referenced

    def on_access(self, vpn: int, is_write: bool) -> None:
        self._ref[vpn] = True

    def victim(self) -> int:
        while True:
            if self._hand >= len(self._slots):
                self._hand = 0
            vpn = self._slots[self._hand]
            if self._ref.get(vpn):
                self._ref[vpn] = False
                self._hand += 1
            else:
                self._slots.pop(self._hand)
                self._ref.pop(vpn, None)
                if self._hand >= len(self._slots):
                    self._hand = 0
                return vpn


class Random(Policy):
    name = "random"

    def __init__(self, capacity: int, seed: int = 0):
        import random
        self._rng = random.Random(seed)
        self._set: list[int] = []

    def on_load(self, vpn: int) -> None:
        self._set.append(vpn)

    def victim(self) -> int:
        i = self._rng.randrange(len(self._set))
        self._set[i], self._set[-1] = self._set[-1], self._set[i]
        return self._set.pop()


class Optimal(Policy):
    """Belady's MIN: evict the page whose next use is furthest in the future
    (or never). Requires the whole trace; a lower bound no online policy beats."""

    name = "optimal"

    def __init__(self, capacity: int):
        self._resident: set[int] = set()
        self._vpn_trace: list[int] = []
        self._cursor = 0

    def set_vpn_trace(self, vpn_trace: list[int]) -> None:
        self._vpn_trace = vpn_trace

    def tick(self, index: int) -> None:
        self._cursor = index

    def on_load(self, vpn: int) -> None:
        self._resident.add(vpn)

    def victim(self) -> int:
        next_use = {vpn: float("inf") for vpn in self._resident}
        pending = len(next_use)
        for dist, vpn in enumerate(self._vpn_trace[self._cursor:]):
            if next_use.get(vpn) == float("inf"):
                next_use[vpn] = dist
                pending -= 1
                if pending == 0:
                    break
        victim = max(self._resident, key=lambda v: next_use[v])
        self._resident.discard(victim)
        return victim


REGISTRY: dict[str, type[Policy]] = {
    cls.name: cls for cls in (FIFO, LRU, Clock, Random, Optimal)
}


def make_policy(name: str, capacity: int) -> Policy:
    try:
        return REGISTRY[name](capacity)
    except KeyError:
        raise ValueError(f"unknown policy {name!r}; choose from {sorted(REGISTRY)}")
