"""Eviction order of each policy on hand-checked sequences."""

from vmsim.replacement import FIFO, LRU, Clock, Optimal, make_policy


def drive(policy, events):
    """events: ('load', vpn) | ('access', vpn) | ('evict', expected_victim)"""
    for kind, arg in events:
        if kind == "load":
            policy.on_load(arg)
        elif kind == "access":
            policy.on_access(arg, False)
        elif kind == "evict":
            assert policy.victim() == arg


def test_fifo_order():
    p = FIFO(3)
    drive(p, [("load", 1), ("load", 2), ("load", 3),
              ("access", 1),                       # access doesn't matter for FIFO
              ("evict", 1), ("evict", 2), ("evict", 3)])


def test_lru_promotes_on_access():
    p = LRU(3)
    drive(p, [("load", 1), ("load", 2), ("load", 3),
              ("access", 1),                       # 1 becomes MRU, 2 is now LRU
              ("evict", 2), ("evict", 3), ("evict", 1)])


def test_clock_second_chance():
    p = Clock(3)
    # load 1,2,3 (all ref=1). victim: hand clears 1,2,3 then evicts 1.
    drive(p, [("load", 1), ("load", 2), ("load", 3), ("evict", 1)])
    # 2 and 3 had their ref bits cleared during that sweep; 2 is next.
    drive(p, [("evict", 2)])
    # ring is now [3]; touch 3 (ref=1) and load 4 (ref=1). The hand sits on 3:
    # it clears 3, clears 4, wraps back to 3 (now ref=0) and evicts it. Then 4.
    drive(p, [("access", 3), ("load", 4), ("evict", 3), ("evict", 4)])


def test_optimal_evicts_furthest_next_use():
    # future VPN stream after "now": 1 appears at dist 0, 3 at dist 1, 2 never
    p = Optimal(3)
    p.set_vpn_trace([9, 9, 1, 3])        # index 2..: 1, 3
    p.tick(2)
    for v in (1, 2, 3):
        p.on_load(v)
    assert p.victim() == 2               # 2 is never used again


def test_optimal_matches_known_min_faults():
    # Silberschatz reference string (first 13 refs), 3 frames.
    # Hand-traced OPT: 7 faults (7,0,1,2 cold; then +3,+4,+0).
    from vmsim.simulator import VirtualMemory
    seq = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2]
    trace = [(False, p * 4096) for p in seq]
    vm = VirtualMemory(3, "optimal", tlb_entries=0)
    vm.run(trace)
    assert vm.stats.page_faults == 7
    # and OPT must not be beaten by any online policy on this string
    from vmsim.simulator import compare_policies
    table = compare_policies(trace, 3, tlb_entries=0)
    assert min(v["page_faults"] for v in table.values()) == 7


def test_registry():
    assert make_policy("fifo", 4).__class__.__name__ == "FIFO"
    try:
        make_policy("nope", 4)
        assert False
    except ValueError:
        pass
