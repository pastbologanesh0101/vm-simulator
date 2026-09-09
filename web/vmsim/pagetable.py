"""Address translation structures: page-table entries, a two-level page table,
and a TLB.

Everything is parameterised by ``page_size`` and the virtual address width so
the same code models a toy 16-bit space or a 32-bit one.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PTE:
    """A page-table entry."""
    frame: int = -1
    present: bool = False
    dirty: bool = False
    referenced: bool = False
    # bookkeeping for the simulator / policies
    loads: int = 0        # how many times this page has been paged in


class TwoLevelPageTable:
    """A radix tree: VPN is split into (top index, bottom index).

    Real hardware walks this structure in memory on every TLB miss; the
    simulator counts those walks as ``page_table_walks`` so the cost of a deep
    table is visible.
    """

    def __init__(self, page_size: int, vaddr_bits: int):
        self.page_size = page_size
        self.offset_bits = (page_size - 1).bit_length()
        self.vpn_bits = vaddr_bits - self.offset_bits
        if self.vpn_bits <= 0:
            raise ValueError("page size too large for the address space")
        # split the VPN roughly in half
        self.bottom_bits = self.vpn_bits // 2
        self.top_bits = self.vpn_bits - self.bottom_bits
        self._top: dict[int, dict[int, PTE]] = {}
        self.walks = 0

    # -- address split ------------------------------------------
    def split(self, vaddr: int) -> tuple[int, int]:
        """Return ``(vpn, offset)``."""
        if vaddr < 0 or vaddr >= (1 << (self.vpn_bits + self.offset_bits)):
            raise ValueError(f"virtual address {vaddr:#x} outside the address space")
        return vaddr >> self.offset_bits, vaddr & (self.page_size - 1)

    def _indices(self, vpn: int) -> tuple[int, int]:
        return vpn >> self.bottom_bits, vpn & ((1 << self.bottom_bits) - 1)

    # -- lookup / creation --------------------------------------
    def get(self, vpn: int) -> PTE:
        """Walk the table, creating empty nodes/entries on the way (like a
        first touch of a fresh page). Counts one walk."""
        self.walks += 1
        top_i, bot_i = self._indices(vpn)
        leaf = self._top.setdefault(top_i, {})
        pte = leaf.get(bot_i)
        if pte is None:
            pte = PTE()
            leaf[bot_i] = pte
        return pte

    def peek(self, vpn: int) -> PTE | None:
        top_i, bot_i = self._indices(vpn)
        return self._top.get(top_i, {}).get(bot_i)

    def resident_vpns(self) -> list[int]:
        out = []
        for top_i, leaf in self._top.items():
            for bot_i, pte in leaf.items():
                if pte.present:
                    out.append((top_i << self.bottom_bits) | bot_i)
        return sorted(out)


class TLB:
    """Fully-associative, LRU replacement. Maps VPN -> (frame, dirty)."""

    def __init__(self, entries: int = 16):
        self.capacity = entries
        self._map: dict[int, list] = {}   # vpn -> [frame, dirty]; dict keeps LRU order
        self.hits = 0
        self.misses = 0

    def lookup(self, vpn: int):
        entry = self._map.pop(vpn, None)
        if entry is None:
            self.misses += 1
            return None
        self._map[vpn] = entry     # move to MRU
        self.hits += 1
        return entry

    def insert(self, vpn: int, frame: int, dirty: bool = False) -> None:
        if self.capacity == 0:
            return
        self._map.pop(vpn, None)
        self._map[vpn] = [frame, dirty]
        if len(self._map) > self.capacity:
            oldest = next(iter(self._map))
            del self._map[oldest]

    def set_dirty(self, vpn: int) -> None:
        if vpn in self._map:
            self._map[vpn][1] = True

    def invalidate(self, vpn: int) -> None:
        self._map.pop(vpn, None)

    def flush(self) -> None:
        self._map.clear()
