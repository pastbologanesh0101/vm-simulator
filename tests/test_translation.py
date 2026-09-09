import pytest

from vmsim.pagetable import TLB, TwoLevelPageTable


def test_address_split():
    pt = TwoLevelPageTable(page_size=4096, vaddr_bits=32)
    assert pt.offset_bits == 12
    assert pt.split(0x0000_0000) == (0, 0)
    assert pt.split(0x0000_1000) == (1, 0)
    assert pt.split(0x0000_1ABC) == (1, 0xABC)
    assert pt.split(0xDEAD_B000) == (0xDEADB, 0)


def test_address_out_of_range():
    pt = TwoLevelPageTable(page_size=256, vaddr_bits=16)
    pt.split(0xFFFF)                     # ok, top of the space
    with pytest.raises(ValueError):
        pt.split(0x1_0000)


def test_two_level_indices_roundtrip():
    pt = TwoLevelPageTable(page_size=4096, vaddr_bits=32)
    for vpn in (0, 1, 255, 4096, 0xFFFFF):
        top, bot = pt._indices(vpn)
        assert (top << pt.bottom_bits) | bot == vpn


def test_pte_created_on_first_touch_and_counts_walks():
    pt = TwoLevelPageTable(4096, 32)
    assert pt.peek(42) is None
    pte = pt.get(42)
    assert pte.present is False and pt.walks == 1
    pt.get(42)
    assert pt.walks == 2                 # every walk is counted


def test_tlb_lru_eviction_and_stats():
    tlb = TLB(entries=2)
    tlb.insert(1, 100); tlb.insert(2, 200)
    assert tlb.lookup(1)[0] == 100       # 1 is now MRU
    tlb.insert(3, 300)                   # evicts 2 (LRU)
    assert tlb.lookup(2) is None
    assert tlb.lookup(3)[0] == 300
    assert tlb.hits == 2 and tlb.misses == 1


def test_tlb_dirty_and_invalidate():
    tlb = TLB(4)
    tlb.insert(7, 70)
    tlb.set_dirty(7)
    assert tlb.lookup(7)[1] is True
    tlb.invalidate(7)
    assert tlb.lookup(7) is None


def test_zero_size_tlb_is_a_noop():
    tlb = TLB(0)
    tlb.insert(1, 1)
    assert tlb.lookup(1) is None
