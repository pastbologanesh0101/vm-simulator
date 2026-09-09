"""The MMU + demand-paging simulator.

For each reference it does what an OS/hardware pair would:

1. Split the virtual address into ``(vpn, offset)``.
2. Check the **TLB**. Hit -> we have the frame, done (a write also sets the
   dirty bit).
3. TLB miss -> **walk the page table**.
4. PTE not present -> **page fault**: find a free frame or run the replacement
   policy to evict one (writing it back to disk first if it's dirty), then page
   the faulting page in from disk.
5. Fill the TLB and finish.

Everything interesting is counted in :class:`Stats`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .pagetable import PTE, TLB, TwoLevelPageTable
from .replacement import Policy, make_policy
from .trace import Reference


@dataclass
class Stats:
    accesses: int = 0
    reads: int = 0
    writes: int = 0
    tlb_hits: int = 0
    tlb_misses: int = 0
    page_faults: int = 0
    cold_faults: int = 0        # fault on a page never seen before
    evictions: int = 0
    disk_reads: int = 0         # page-ins
    disk_writes: int = 0        # dirty write-backs
    page_table_walks: int = 0

    @property
    def fault_rate(self) -> float:
        return self.page_faults / self.accesses if self.accesses else 0.0

    @property
    def tlb_hit_rate(self) -> float:
        total = self.tlb_hits + self.tlb_misses
        return self.tlb_hits / total if total else 0.0

    @property
    def effective_access_cost(self) -> float:
        """A toy EAT in 'ns': TLB 1, memory 100, disk 1_000_000."""
        return (
            self.accesses * 1
            + self.page_table_walks * 100
            + self.disk_reads * 1_000_000
            + self.disk_writes * 1_000_000
        ) / self.accesses if self.accesses else 0.0

    def as_dict(self) -> dict:
        d = {k: getattr(self, k) for k in self.__dataclass_fields__}
        d["fault_rate"] = round(self.fault_rate, 4)
        d["tlb_hit_rate"] = round(self.tlb_hit_rate, 4)
        d["eat_ns"] = round(self.effective_access_cost, 1)
        return d


class VirtualMemory:
    def __init__(self, num_frames: int, policy: str = "lru", *,
                 page_size: int = 4096, vaddr_bits: int = 32, tlb_entries: int = 16):
        if num_frames < 1:
            raise ValueError("need at least one physical frame")
        self.num_frames = num_frames
        self.page_size = page_size
        self.pt = TwoLevelPageTable(page_size, vaddr_bits)
        self.tlb = TLB(tlb_entries)
        self.policy: Policy = make_policy(policy, num_frames)
        self.free_frames = list(range(num_frames))
        self.frame_owner: dict[int, int] = {}   # frame -> vpn
        self.seen_vpns: set[int] = set()
        self.stats = Stats()

    # -- one reference ----------------------------------------
    def access(self, is_write: bool, vaddr: int) -> None:
        s = self.stats
        s.accesses += 1
        s.writes += is_write
        s.reads += not is_write

        vpn, _ = self.pt.split(vaddr)

        # 1-2. TLB
        entry = self.tlb.lookup(vpn)
        if entry is not None:
            s.tlb_hits += 1
            if is_write:
                self.tlb.set_dirty(vpn)
                self.pt.peek(vpn).dirty = True
            self.policy.on_access(vpn, is_write)
            return
        s.tlb_misses += 1

        # 3. page-table walk
        pte = self.pt.get(vpn)
        s.page_table_walks = self.pt.walks

        if not pte.present:
            self._page_fault(vpn, pte)
        else:
            self.policy.on_access(vpn, is_write)

        # 5. finish: update PTE + TLB
        pte.referenced = True
        if is_write:
            pte.dirty = True
        self.tlb.insert(vpn, pte.frame, pte.dirty)

    # -- fault handling ------------------------------------
    def _page_fault(self, vpn: int, pte: PTE) -> None:
        s = self.stats
        s.page_faults += 1
        if vpn not in self.seen_vpns:
            s.cold_faults += 1
            self.seen_vpns.add(vpn)

        if self.free_frames:
            frame = self.free_frames.pop()
        else:
            frame = self._evict()

        s.disk_reads += 1               # page the faulting page in
        pte.frame = frame
        pte.present = True
        pte.dirty = False
        pte.referenced = True
        pte.loads += 1
        self.frame_owner[frame] = vpn
        self.policy.on_load(vpn)

    def _evict(self) -> int:
        s = self.stats
        victim_vpn = self.policy.victim()
        victim_pte = self.pt.peek(victim_vpn)
        frame = victim_pte.frame

        if victim_pte.dirty:
            s.disk_writes += 1          # write-back before reuse

        victim_pte.present = False
        victim_pte.frame = -1
        self.tlb.invalidate(victim_vpn)
        self.frame_owner.pop(frame, None)
        s.evictions += 1
        return frame

    # -- driving a whole trace --------------------------
    def run(self, trace: list[Reference]) -> Stats:
        vpn_trace = [addr >> self.pt.offset_bits for _, addr in trace]
        self.policy.set_vpn_trace(vpn_trace)
        for i, (is_write, vaddr) in enumerate(trace):
            self.policy.tick(i + 1)     # future starts after the current ref
            self.access(is_write, vaddr)
        return self.stats

    # -- introspection --------------------------------
    def resident_set(self) -> list[int]:
        return sorted(self.frame_owner.values())


def compare_policies(trace: list[Reference], num_frames: int,
                     policies: list[str] | None = None, **kw) -> dict[str, dict]:
    names = policies or ["fifo", "lru", "clock", "random", "optimal"]
    result = {}
    for name in names:
        vm = VirtualMemory(num_frames, name, **kw)
        vm.run(trace)
        result[name] = vm.stats.as_dict()
    return result
