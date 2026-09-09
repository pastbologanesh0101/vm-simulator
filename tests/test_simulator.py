import pytest

from vmsim.simulator import VirtualMemory, compare_policies
from vmsim import trace as tracemod


PS = 4096


def refs(pages, write=False):
    return [(write, p * PS) for p in pages]


def test_cold_faults_then_hits():
    vm = VirtualMemory(4, "lru", tlb_entries=0)
    vm.run(refs([0, 1, 2, 0, 1, 2]))
    assert vm.stats.page_faults == 3
    assert vm.stats.cold_faults == 3
    assert vm.stats.disk_reads == 3
    assert vm.stats.fault_rate == 0.5


def test_eviction_and_disk_writeback_on_dirty():
    vm = VirtualMemory(2, "fifo", tlb_entries=0)
    # write pages 0,1 (both dirty), then read 2 -> evict 0 (dirty -> write-back),
    # then read 0 again -> evict 1 (dirty -> write-back)
    vm.run([(True, 0 * PS), (True, 1 * PS), (False, 2 * PS), (False, 0 * PS)])
    assert vm.stats.evictions == 2
    assert vm.stats.disk_writes == 2
    assert vm.stats.disk_reads == 4          # 3 cold + 1 re-fault on page 0


def test_clean_eviction_has_no_writeback():
    vm = VirtualMemory(2, "fifo", tlb_entries=0)
    vm.run(refs([0, 1, 2, 3]))               # all reads -> clean
    assert vm.stats.evictions == 2
    assert vm.stats.disk_writes == 0


def test_tlb_hits_skip_page_table_walks():
    vm = VirtualMemory(4, "lru", tlb_entries=8)
    vm.run(refs([1, 1, 1, 1, 1]))
    assert vm.stats.tlb_hits == 4
    assert vm.stats.tlb_misses == 1
    assert vm.stats.page_faults == 1
    assert vm.stats.page_table_walks == 1    # only the first, cold access walks


def test_more_frames_never_hurt_lru():
    trace = tracemod.working_set(3000, seed=1)
    prev = None
    for frames in (4, 8, 16, 32, 64):
        vm = VirtualMemory(frames, "lru")
        vm.run(trace)
        if prev is not None:
            assert vm.stats.page_faults <= prev   # LRU is a stack algorithm
        prev = vm.stats.page_faults


def test_optimal_is_a_lower_bound():
    trace = tracemod.working_set(2000, seed=7)
    table = compare_policies(trace, 12)
    opt = table["optimal"]["page_faults"]
    for name in ("fifo", "lru", "clock", "random"):
        assert table[name]["page_faults"] >= opt


def test_belady_anomaly_reproduces():
    seq = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
    trace = refs(seq)
    f3 = VirtualMemory(3, "fifo", tlb_entries=0); f3.run(trace)
    f4 = VirtualMemory(4, "fifo", tlb_entries=0); f4.run(trace)
    assert f4.stats.page_faults > f3.stats.page_faults    # the anomaly


def test_resident_set_never_exceeds_frames():
    trace = tracemod.uniform_random(4000, span_pages=500, seed=3)
    for pol in ("fifo", "lru", "clock", "optimal"):
        vm = VirtualMemory(10, pol)
        vm.run(trace)
        assert len(vm.resident_set()) <= 10
        assert vm.stats.disk_reads == vm.stats.page_faults


def test_all_hits_after_working_set_fits():
    vm = VirtualMemory(16, "lru")
    hot = list(range(8))
    vm.run(refs(hot * 50))
    assert vm.stats.page_faults == 8        # 8 cold faults, then everything resident
