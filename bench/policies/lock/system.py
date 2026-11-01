"""락 정책의 공통 기반: 락 표(LockTable)와 정책 호출 규약 (RQ3, docs/rq3/policies.md §2).

락 표는 락 관리자가 가진 상태다. 정책은 이 상태를 읽고 결정만 돌려준다. 같은 정책 코드가
소규모 전수 검사(bench/check_lock_policies.py)와 이후의 이산 사건 시뮬레이션에서 쓰인다.

용어.
  스레드 t(0..T-1)는 프로그램 하나를 실행한다. 프로그램은 ('A', l)(락 얻기)와 ('R', l)(반납)의 열이다.
  락 l(0..L-1)은 배타적이고 재진입 불가이며 번호가 곧 전역 클래스 순서다(P-ORD의 순서).
  phase: START(시작 전 또는 중단 뒤 재시작 대기), RUN(다음 연산을 실행할 수 있음), BLOCKED(요청이 허가되지
         않아 대기 중), DONE(끝남), FAILED(작업 실패).
  blocked: 대기 중인 스레드의 도착 순서 목록. want[t]는 t가 한꺼번에 얻으려는 락 집합(보통 하나,
         P-ALL의 시작 요청은 작업의 전체 집합), bkey[t]는 정책이 정한 정렬 키(작을수록 먼저).
  타임스탬프 ts[t]는 작을수록 나이가 많다. 소규모 전수 검사에서는 ts[t] = t다(스레드마다 가능한 모든
  프로그램을 열거하므로 모든 나이 순서가 덮인다). 중단과 재시작에도 ts는 유지된다(prereg/RQ3.md O3-5의 제안).
  우선순위 prio[t]는 클수록 높다(기본 T - t).

정책 규약(Policy). 정책은 락 표의 상태에서만 결정을 낸다(정책 객체는 변하는 상태를 갖지 않는다).
  begin(tb, t)            작업 시작. 일괄 요청 정책이 전체 집합을 요청한다.
  request(tb, t, l)       RUN 스레드의 ('A', l) 요청에 대한 결정 Decision.
  admissible(tb, t, want) 락이 모두 비어 있을 때 추가로 필요한 허가 조건(천장, 안전 상태 등)
  key(tb, t, l)           대기열 정렬 키. None이면 도착 순서.
  detect(tb)              탐지 정책이 중단시킬 희생자 목록(없으면 빈 튜플)
  invariant(tb)           정책이 유지해야 하는 상태 불변식의 위반 설명(없으면 None)
결정(Decision)은 GRANT, WAIT, DENY(자기 중단 후 재시작), FAIL(작업 실패. 재시도 없음), WOUND(희생자 중단 후
요청자는 대기열에 들어감)이다.
"""
from __future__ import annotations

from dataclasses import dataclass

START, RUN, BLOCKED, DONE, FAILED = 0, 1, 2, 3, 4
PHASE_NAMES = {START: "START", RUN: "RUN", BLOCKED: "BLOCKED", DONE: "DONE", FAILED: "FAILED"}

GRANT, WAIT, DENY, FAIL, WOUND = "GRANT", "WAIT", "DENY", "FAIL", "WOUND"


@dataclass(frozen=True)
class Decision:
    kind: str
    victims: tuple = ()


D_GRANT = Decision(GRANT)
D_WAIT = Decision(WAIT)
D_DENY = Decision(DENY)
D_FAIL = Decision(FAIL)


def wound(*victims):
    return Decision(WOUND, tuple(victims))


def programs_claim(progs):
    return tuple(frozenset(l for k, l in p if k == "A") for p in progs)


class LockTable:
    """락 관리자의 상태. snapshot()/restore()로 전수 탐색에서 쓴다."""

    def __init__(self, progs, ts=None, prio=None, nlocks=None):
        self.progs = tuple(tuple(tuple(op) for op in p) for p in progs)
        self.T = len(self.progs)
        self.L = nlocks if nlocks is not None else 1 + max((l for p in self.progs for _, l in p), default=-1)
        self.claim_all = programs_claim(self.progs)           # 작업이 쓸 락 집합(K1 선언, K2 사용 정보)
        self.ts = tuple(ts) if ts is not None else tuple(range(self.T))
        self.prio = tuple(prio) if prio is not None else tuple(self.T - t for t in range(self.T))
        self.phase = [START] * self.T
        self.pc = [0] * self.T
        self.holder = [None] * self.L
        self.blocked: list[int] = []
        self.want: list = [None] * self.T
        self.bkey: list = [None] * self.T
        self.bkind: list = [None] * self.T                     # 'op'(ACQ 연산 대기) 또는 'begin'(시작 요청)

    # ------------------------------------------------------------ 조회
    def held_of(self, t):
        return frozenset(l for l in range(self.L) if self.holder[l] == t)

    def claim(self, t):
        """스레드 t의 현재 작업이 선언한 락 집합. 활성(RUN, BLOCKED)일 때만 뜻이 있다."""
        return self.claim_all[t] if self.phase[t] in (RUN, BLOCKED) else frozenset()

    def terminal(self):
        return all(p in (DONE, FAILED) for p in self.phase)

    def unfinished(self):
        return [t for t in range(self.T) if self.phase[t] not in (DONE, FAILED)]

    def next_op(self, t):
        return self.progs[t][self.pc[t]] if self.pc[t] < len(self.progs[t]) else None

    def ceiling(self, l):
        """락 l의 천장: l을 쓰는 스레드의 최대 우선순위(K2: 모든 스레드의 사용 선언)."""
        users = [self.prio[t] for t in range(self.T) if l in self.claim_all[t]]
        return max(users) if users else -1

    def wfg_edges(self):
        """대기 그래프 간선 (t, u): t가 원하는 락을 u가 쥐고 있다(u != t)."""
        edges = []
        for t in self.blocked:
            for l in sorted(self.want[t]):
                u = self.holder[l]
                if u is not None and u != t:
                    edges.append((t, u))
        return edges

    # ------------------------------------------------------------ 변경
    def block(self, t, want, key=None, kind="op"):
        assert self.phase[t] in (RUN, START), f"스레드 {t}가 {PHASE_NAMES[self.phase[t]]}에서 대기에 들어감"
        self.phase[t] = BLOCKED
        self.want[t] = frozenset(want)
        self.bkey[t] = key
        self.bkind[t] = kind
        self.blocked.append(t)

    def _unblock(self, t):
        self.blocked.remove(t)
        self.want[t] = None
        self.bkey[t] = None
        self.bkind[t] = None

    def grant_direct(self, t, l):
        assert self.holder[l] is None, f"락 {l}이 비어 있지 않은데 허가"
        self.holder[l] = t
        self.pc[t] += 1

    def grant_blocked(self, t):
        want = self.want[t]
        kind = self.bkind[t]
        for l in want:
            assert self.holder[l] is None
            self.holder[l] = t
        self._unblock(t)
        if kind == "op":
            self.pc[t] += 1
        self.phase[t] = RUN

    def release(self, t, l):
        assert self.holder[l] == t, f"스레드 {t}가 쥐지 않은 락 {l}을 반납"
        self.holder[l] = None
        self.pc[t] += 1

    def _drop_all(self, t):
        for l in range(self.L):
            if self.holder[l] == t:
                self.holder[l] = None
        if self.phase[t] == BLOCKED:
            self._unblock(t)

    def abort(self, t):
        """중단: 쥔 락을 모두 반납하고 처음부터 다시 시작할 수 있는 상태로 돌아간다(ts 유지)."""
        self._drop_all(t)
        self.pc[t] = 0
        self.phase[t] = START

    def fail(self, t):
        self._drop_all(t)
        self.phase[t] = FAILED

    def finish(self, t):
        # 프로그램은 끝날 때 쥔 락이 없다. 남아 있으면 모델 오류다.
        assert not self.held_of(t), f"스레드 {t}가 락을 쥔 채 끝남"
        self.phase[t] = DONE

    # ------------------------------------------------------------ 스냅샷
    def snapshot(self):
        return (tuple(self.phase), tuple(self.pc), tuple(self.holder),
                tuple((t, tuple(sorted(self.want[t])), self.bkey[t], self.bkind[t]) for t in self.blocked))

    def restore(self, snap):
        phase, pc, holder, blocked = snap
        self.phase = list(phase)
        self.pc = list(pc)
        self.holder = list(holder)
        self.blocked = [b[0] for b in blocked]
        self.want = [None] * self.T
        self.bkey = [None] * self.T
        self.bkind = [None] * self.T
        for t, want, key, kind in blocked:
            self.want[t] = frozenset(want)
            self.bkey[t] = key
            self.bkind[t] = kind

    # ------------------------------------------------------------ 스냅샷 모델과의 연결
    def to_sm(self):
        """모델 명세 §2의 스냅샷으로. 대기 중인 스레드의 요청은 want의 AND 벡터 하나다."""
        import os
        import sys
        here = os.path.dirname(os.path.abspath(__file__))
        oracle_dir = os.path.normpath(os.path.join(here, "..", "..", "..", "oracle"))
        if oracle_dir not in sys.path:
            sys.path.insert(0, oracle_dir)
        from sm import Inst
        L = max(self.L, 1)
        alloc = tuple(tuple(1 if self.holder[l] == t else 0 for l in range(L)) for t in range(self.T))
        alts = []
        for t in range(self.T):
            if self.phase[t] == BLOCKED:
                w = self.want[t]
                alts.append(frozenset({tuple(1 if l in w else 0 for l in range(L))}))
            else:
                alts.append(frozenset())
        return Inst(cap=(1,) * L, alloc=alloc, alts=tuple(alts))

    def show(self):
        parts = []
        for t in range(self.T):
            ph = PHASE_NAMES[self.phase[t]]
            h = sorted(self.held_of(t))
            w = f" want{sorted(self.want[t])}" if self.phase[t] == BLOCKED else ""
            parts.append(f"T{t}:{ph} pc={self.pc[t]} hold{h}{w}")
        return "; ".join(parts)


# ---------------------------------------------------------------- 정책 기반 클래스

class Policy:
    name = "base"
    info = "K0"
    kind = "none"          # 'prevention' | 'avoidance' | 'detection' | 'none'
    detects = False
    batch = False          # True이면 작업 시작에 전체 락 집합을 요청한다(P-ALL)

    def begin(self, tb: LockTable, t: int) -> None:
        return None

    def key(self, tb: LockTable, t: int, l: int):
        return None

    def admissible(self, tb: LockTable, t: int, want) -> bool:
        return True

    def request(self, tb: LockTable, t: int, l: int) -> Decision:
        if tb.holder[l] is None and self.admissible(tb, t, frozenset({l})):
            return D_GRANT
        return D_WAIT

    def detect(self, tb: LockTable) -> tuple:
        return ()

    def invariant(self, tb: LockTable):
        return None


# ---------------------------------------------------------------- 락 관리자의 공통 동작

def settle(tb: LockTable, pol: Policy) -> int:
    """대기 중인 스레드 가운데 허가할 수 있는 것을 정렬 키 순서로 하나씩 허가한다. 허가 수를 돌려준다."""
    n = 0
    while True:
        order = sorted(tb.blocked, key=lambda t: (tb.bkey[t] if tb.bkey[t] is not None else 0))
        for t in order:
            want = tb.want[t]
            if all(tb.holder[l] is None for l in want) and pol.admissible(tb, t, want):
                tb.grant_blocked(t)
                n += 1
                break
        else:
            return n


def apply_decision(tb: LockTable, pol: Policy, t: int, l: int, d: Decision) -> list:
    """결정을 락 표에 적용한다. 중단된 스레드를 (스레드, 사유) 목록으로 돌려준다.

    사유: 'deny'(자기 중단 후 재시작), 'fail'(작업 실패), 'wound'(다른 스레드가 중단시킴)."""
    aborted = []
    if d.kind == GRANT:
        tb.grant_direct(t, l)
    elif d.kind == WAIT:
        tb.block(t, {l}, key=pol.key(tb, t, l), kind="op")
    elif d.kind == DENY:
        tb.abort(t)
        aborted.append((t, "deny"))
    elif d.kind == FAIL:
        tb.fail(t)
        aborted.append((t, "fail"))
    elif d.kind == WOUND:
        for v in d.victims:
            tb.abort(v)
            aborted.append((v, "wound"))
        tb.block(t, {l}, key=pol.key(tb, t, l), kind="op")
    else:  # pragma: no cover
        raise ValueError(d.kind)
    return aborted


def step_thread(tb: LockTable, pol: Policy, t: int) -> list:
    """스레드 t가 한 걸음 진행한다(START 또는 RUN). 이 걸음에서 중단된 (스레드, 사유) 목록을 돌려준다."""
    aborted: list = []
    ph = tb.phase[t]
    if ph == START:
        tb.phase[t] = RUN
        pol.begin(tb, t)
    elif ph == RUN:
        op = tb.next_op(t)
        if op is None:
            tb.finish(t)
        elif op[0] == "R":
            tb.release(t, op[1])
        else:
            l = op[1]
            if pol.batch and tb.holder[l] == t:
                tb.pc[t] += 1                       # 시작 때 이미 얻은 락
            else:
                assert tb.holder[l] != t, f"스레드 {t}가 이미 쥔 락 {l}을 다시 요청(프로그램 오류)"
                d = pol.request(tb, t, l)
                aborted = apply_decision(tb, pol, t, l, d)
    else:  # pragma: no cover
        raise ValueError(f"스레드 {t}는 {PHASE_NAMES[ph]} 상태라 진행할 수 없음")
    settle(tb, pol)
    return aborted


def detect_step(tb: LockTable, pol: Policy) -> list:
    victims = list(pol.detect(tb))
    for v in victims:
        tb.abort(v)
    settle(tb, pol)
    return [(v, "detect") for v in victims]
