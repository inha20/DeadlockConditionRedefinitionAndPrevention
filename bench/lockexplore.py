"""락 정책의 명시적 상태 전수 탐색 (RQ3 WP3.1, prereg/README.md SP-5의 ①).

워크로드 하나(스레드마다 직선 락 프로그램 하나)와 정책 하나에서 도달 가능한 모든 락 표 상태를
너비 우선으로 열거한다. 비결정성은 '어느 스레드가 다음에 한 걸음 가는가'(step)와 탐지 정책의
탐지 시점(detect)뿐이다. 중단된 스레드의 백오프는 임의 지연이라 걸음의 선택에 흡수된다.

검사하는 성질(상태 또는 전이마다).
  inv        정책의 상태 불변식(Policy.invariant)이 깨지지 않는다
  deadlock   스냅샷 모델(모델 명세 §3.1, oracle/sm.py)의 교착 집합이 상태에 없다(예방·회피 정책)
  stall      끝나지 않았는데 가능한 동작이 없는 상태가 없다(정책이 허가를 미뤄 모두 멈추는 경우 포함)
  trap       모든 도달 가능 상태에서 끝난 상태(모든 스레드가 DONE 또는 FAILED)로 가는 경로가 있다
             (기아 부재가 아니라 '영구 함정 없음'이다. 공정성 아래의 기아 검사는 하지 않는다)
  oldest     (oldest_safe 표지가 있는 정책) 끝나지 않은 스레드 중 가장 나이 많은 스레드가 중단되지 않는다
  audit      회피 정책의 허가 결정이 정확 오라클 O1과 같다, P-RAG와 P-BNK의 결정이 같다
  oracle     O2(oracle/locks.py)와의 일관성: 교착 집합이 있는 상태는 O2에서 불안전, 회피 정책의 모든
             도달 가능 상태는 O2에서 안전
탐색 결과의 첫 반례는 가장 짧은 동작열로 복원한다.
"""
from __future__ import annotations

import os
import sys
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "oracle"))

import sm  # noqa: E402
import banker as ob  # noqa: E402
import locks as o2  # noqa: E402
from bench.policies.lock.system import (BLOCKED, DONE, FAILED, RUN, START, LockTable,  # noqa: E402
                                        detect_step, step_thread)
from bench.policies.lock.policies import banker_safe, claim_wait_cycle  # noqa: E402

PROPS = ("inv", "deadlock", "stall", "trap", "oldest", "audit", "oracle")


def enabled(tb, pol):
    acts = [("step", t) for t in range(tb.T) if tb.phase[t] in (START, RUN)]
    if pol.detects and pol.detect(tb):
        acts.append(("detect", None))
    return acts


def apply(tb, pol, act):
    if act[0] == "step":
        return step_thread(tb, pol, act[1])
    return detect_step(tb, pol)


def describe_action(act):
    return f"T{act[1]} 진행" if act[0] == "step" else "탐지 실행"


def _o1_safe_after(tb, t, l):
    """스레드 t가 락 l을 얻는다고 가정한 뒤의 상태를 오라클 O1(뱅커 모델, s_max 변환)로 판정한다."""
    T, L = tb.T, tb.L
    alloc = []
    maxc = []
    for u in range(T):
        held = set(tb.held_of(u))
        cl = set(tb.claim(u))
        if u == t:
            held.add(l)
            cl.add(l)
        alloc.append(tuple(1 if r in held else 0 for r in range(L)))
        maxc.append(tuple(1 if (r in cl or r in held) else 0 for r in range(L)))
    b = ob.Banker(total=(1,) * L, alloc=tuple(alloc), maxc=tuple(maxc))
    return ob.safe_oracle(b)


def _candidates(tb):
    """허가 결정이 의미 있는 (스레드, 락): 다음 연산이 비어 있는 락의 요청인 RUN 스레드, 비어 있는 락을 기다리는 스레드."""
    out = []
    for t in range(tb.T):
        if tb.phase[t] == RUN:
            op = tb.next_op(t)
            if op is not None and op[0] == "A" and tb.holder[op[1]] is None:
                out.append((t, op[1]))
        elif tb.phase[t] == BLOCKED and tb.bkind[t] == "op":
            (l,) = tuple(tb.want[t])
            if tb.holder[l] is None:
                out.append((t, l))
    return out


class Result:
    def __init__(self):
        self.states = 0
        self.edges = 0
        self.terminal = 0
        self.deadlock_states = 0          # SM 교착 집합이 있는 상태 수
        self.first = {}                   # 성질 -> (설명, 동작열)
        self.counts = {p: 0 for p in PROPS}
        self.audit_calls = 0
        self.abort_events = 0
        self.max_blocked = 0

    def note(self, prop, msg, trace_fn):
        self.counts[prop] += 1
        if prop not in self.first:
            self.first[prop] = (msg, trace_fn())


def explore(progs, pol, nlocks=None, audit=True, oracle=True, max_states=200000):
    oldest_safe = getattr(pol, "oldest_safe", False)
    tb = LockTable(progs, nlocks=nlocks)
    res = Result()
    O2 = o2.LockProgSystem(progs) if oracle else None
    init = tb.snapshot()
    snaps = [init]
    index = {init: 0}
    parent = [None]
    succ = [[]]
    is_term = []
    dl_cache = {}
    queue = deque([0])

    def trace_to(i, extra=None):
        acts = []
        while parent[i] is not None:
            pi, act = parent[i]
            acts.append(act)
            i = pi
        acts.reverse()
        if extra is not None:
            acts.append(extra)
        return [describe_action(a) for a in acts]

    batch = pol.batch
    while queue:
        i = queue.popleft()
        snap = snaps[i]
        tb.restore(snap)
        # ---- 상태 성질
        msg = pol.invariant(tb)
        if msg:
            res.note("inv", msg, lambda i=i: trace_to(i))
        if tb.blocked:
            res.max_blocked = max(res.max_blocked, len(tb.blocked))
            key = (snap[2], snap[3])
            dl = dl_cache.get(key)
            if dl is None:
                dl = sm.has_deadlock(tb.to_sm())
                dl_cache[key] = dl
            if dl:
                res.deadlock_states += 1
                if not pol.detects:
                    res.note("deadlock", "교착 집합이 있는 상태: " + tb.show(), lambda i=i: trace_to(i))
        else:
            dl = False
        term = tb.terminal()
        is_term.append(term)
        if term:
            res.terminal += 1
        acts = [] if term else enabled(tb, pol)
        if not term and not acts:
            res.note("stall", "가능한 동작이 없음: " + tb.show(), lambda i=i: trace_to(i))
        # ---- 정확 오라클과의 대조
        if audit and not term and getattr(pol, "audit_o1", False):
            for (t, l) in _candidates(tb):
                res.audit_calls += 1
                got = pol.admissible(tb, t, frozenset({l}))
                want_safe = _o1_safe_after(tb, t, l)
                if got != want_safe:
                    res.note("audit", f"스레드 {t}의 락 {l} 허가 결정 {got}이 오라클 O1 {want_safe}과 다름: " + tb.show(),
                             lambda i=i: trace_to(i))
                if getattr(pol, "audit_vs_bnk", False) and banker_safe(tb, grant=(t, frozenset({l}))) != got:
                    res.note("audit", f"P-RAG와 P-BNK 결정이 다름(스레드 {t}, 락 {l}): " + tb.show(),
                             lambda i=i: trace_to(i))
        if oracle and not batch:
            # 작업이 실패한(FAILED) 스레드는 프로그램을 버렸으므로 O2에서는 끝난 것으로 본다.
            pcs = tuple(O2.end[u] if tb.phase[u] == FAILED else tb.pc[u] for u in range(tb.T))
            # 락 표의 쥔 락이 O2의 pcs가 정하는 쥔 락과 같은지(일관성)
            hm = O2.held_masks(pcs)
            for u in range(tb.T):
                m = 0
                for l in tb.held_of(u):
                    m |= 1 << l
                if m != hm[u]:
                    res.note("oracle", f"락 표와 O2의 쥔 락이 다름(스레드 {u}): " + tb.show(), lambda i=i: trace_to(i))
                    break
            else:
                if dl and O2.safe(pcs):
                    res.note("oracle", "교착 집합이 있는데 O2가 안전으로 판정: " + tb.show(), lambda i=i: trace_to(i))
                if pol.kind == "avoidance" and not O2.safe(pcs):
                    res.note("oracle", "회피 정책의 상태가 O2에서 불안전: " + tb.show(), lambda i=i: trace_to(i))
        # ---- 전이
        oldest = None
        if oldest_safe:
            unf = tb.unfinished()
            oldest = min(unf, key=lambda u: tb.ts[u]) if unf else None
        for act in acts:
            tb.restore(snap)
            aborted = apply(tb, pol, act)
            res.edges += 1
            if aborted:
                res.abort_events += len(aborted)
                if oldest_safe:
                    for v, why in aborted:
                        if v == oldest and why in ("deny", "wound"):
                            res.note("oldest", f"가장 나이 많은 스레드 {v}가 중단됨({why})", lambda i=i, a=act: trace_to(i, a))
            ns = tb.snapshot()
            j = index.get(ns)
            if j is None:
                j = len(snaps)
                index[ns] = j
                snaps.append(ns)
                parent.append((i, act))
                succ.append([])
                queue.append(j)
                if len(snaps) > max_states:
                    raise RuntimeError(f"상태 수가 한도 {max_states}를 넘음")
            succ[i].append(j)
    res.states = len(snaps)
    # ---- 영구 함정: 끝난 상태로 가는 경로가 없는 상태
    n = len(snaps)
    rev = [[] for _ in range(n)]
    for i in range(n):
        for j in succ[i]:
            rev[j].append(i)
    ok = [False] * n
    dq = deque([i for i in range(n) if is_term[i]])
    for i in dq:
        ok[i] = True
    while dq:
        j = dq.popleft()
        for i in rev[j]:
            if not ok[i]:
                ok[i] = True
                dq.append(i)
    for i in range(n):
        if not ok[i]:
            tb.restore(snaps[i])
            res.note("trap", "끝난 상태로 갈 수 없는 상태: " + tb.show(), lambda i=i: trace_to(i))
    return res
