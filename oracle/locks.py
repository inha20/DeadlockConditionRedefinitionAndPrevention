"""단일 인스턴스 락 프로그램의 정확 오라클 O2 (문서 02 SI-2, prereg/RQ3.md §5의 M1).

모델. 스레드 t마다 분기 없는 직선 프로그램 prog[t]가 있다. 프로그램은 연산의 열이고 연산은
  ('A', l)  락 l을 얻는다(다른 스레드가 쥐고 있으면 기다린다)
  ('R', l)  락 l을 반납한다
락은 배타적이고 재진입 불가이며 선점되지 않는다(모델 명세 A1, A2). 한 프로그램은 같은 락을 두 번
얻지 않고, 얻지 않은 락을 반납하지 않으며, 끝날 때 쥔 락이 없다(valid_program).

상태는 스레드별 진행 위치 pcs(pcs[t] = 이미 끝낸 연산 수)다. 쥔 락은 pcs에서 정해진다.
  이동: 스레드 t의 다음 연산이 ('R', l)이면 언제나 가능, ('A', l)이면 l을 아무도 쥐지 않을 때 가능.
  끝난 상태: 모든 스레드가 프로그램 끝에 있다.
판정(이 모듈이 정의하는 것).
  safe(pcs)               pcs에서 모든 스레드가 끝나는 스케줄이 있다(회피 관점의 안전)
  stuck(pcs)              끝난 상태가 아니고 가능한 이동이 없다(전체 교착)
  has_deadlock_set(pcs)   스냅샷 모델(모델 명세 §3.1)의 교착 집합이 있다(부분 교착 포함)
  possible_deadlock(pcs)  pcs에서 도달 가능한 상태 중 교착 집합이 있는 상태가 있다
  request_permissible(pcs, t)  prereg/RQ3.md §5 M1의 '오라클 허용 가능': 스레드 t의 다음 연산이
                          ('A', l)일 때 l이 비어 있으면 허가한 뒤의 상태가 safe, 쥐어져 있으면 지금
                          상태가 safe(t가 기다리는 상태). 정책을 모르고 프로그램 전체를 아는 판정이다.
확인 가능한 관계(oracle/check_locks.py가 검사): stuck => has_deadlock_set, not safe => possible_deadlock,
그리고 possible_deadlock(pcs) <=> pcs에서 도달 가능한 전체 교착(stuck) 상태가 있다(도출(AI): 부분 교착 집합 밖의
스레드를 끝까지 돌리면 전체 교착에 이른다).

한계. 상태 수는 스레드별 (프로그램 길이 + 1)의 곱이다(스레드 4개, 연산 6개씩이면 최대 7^4 = 2,401).
일반 순차 자원 할당의 안전성 판정은 NP-완전이므로(문헌 M9) 이 오라클은 소규모에 한정한다.
이 오라클은 모델 명세의 정의를 그대로 옮긴 것이고 문헌의 안전 정의와 같다는 뜻이 아니다.
"""
from __future__ import annotations

import os
import sys
from functools import lru_cache

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sm  # noqa: E402
from sm import Inst  # noqa: E402

Op = tuple
Prog = tuple


def valid_program(prog: Prog) -> str | None:
    """프로그램이 형식에 맞으면 None, 아니면 사유."""
    held: set = set()
    for k, l in prog:
        if k == "A":
            if l in held:
                return f"락 {l}을 이미 쥔 채 다시 얻음"
            held.add(l)
        elif k == "R":
            if l not in held:
                return f"쥐지 않은 락 {l}을 반납"
            held.discard(l)
        else:
            return f"알 수 없는 연산 {k!r}"
    if held:
        return f"끝날 때 쥔 락이 남음 {sorted(held)}"
    return None


class LockProgSystem:
    """락 프로그램 모음 하나에 대한 오라클. 같은 모음에 대한 질의는 메모를 공유한다."""

    def __init__(self, progs):
        self.progs = tuple(tuple(tuple(op) for op in p) for p in progs)
        for t, p in enumerate(self.progs):
            problem = valid_program(p)
            if problem:
                raise ValueError(f"프로그램 {t}: {problem}")
        self.T = len(self.progs)
        self.L = 1 + max((l for p in self.progs for _, l in p), default=-1)
        self.end = tuple(len(p) for p in self.progs)
        # 위치별 쥔 락(비트마스크). held_mask[t][pc]
        self.held_mask = []
        for p in self.progs:
            masks = [0]
            cur = 0
            for k, l in p:
                cur = cur | (1 << l) if k == "A" else cur & ~(1 << l)
                masks.append(cur)
            self.held_mask.append(masks)
        self._safe: dict = {}
        self._reach: dict = {}
        self._dead: dict = {}

    # ------------------------------------------------------------ 기본
    def held_masks(self, pcs):
        return [self.held_mask[t][pcs[t]] for t in range(self.T)]

    def finished(self, pcs) -> bool:
        return all(pcs[t] == self.end[t] for t in range(self.T))

    def moves(self, pcs):
        """가능한 이동 [(t, 새 pcs)]."""
        hm = self.held_masks(pcs)
        out = []
        for t in range(self.T):
            if pcs[t] == self.end[t]:
                continue
            k, l = self.progs[t][pcs[t]]
            if k == "A":
                others = 0
                for u in range(self.T):
                    if u != t:
                        others |= hm[u]
                if others >> l & 1:
                    continue
            out.append((t, pcs[:t] + (pcs[t] + 1,) + pcs[t + 1:]))
        return out

    def stuck(self, pcs) -> bool:
        return (not self.finished(pcs)) and not self.moves(pcs)

    def valid_state(self, pcs) -> bool:
        hm = self.held_masks(pcs)
        acc = 0
        for m in hm:
            if acc & m:
                return False
            acc |= m
        return True

    # ------------------------------------------------------------ 안전
    def safe(self, pcs) -> bool:
        pcs = tuple(pcs)
        memo = self._safe
        if pcs in memo:
            return memo[pcs]
        # 반복 DFS(위치가 증가하는 DAG). 재귀 깊이를 피한다.
        stack = [pcs]
        order = []
        seen = {pcs}
        succ_of: dict = {}
        while stack:
            s = stack.pop()
            if s in memo:
                continue
            order.append(s)
            ms = [n for _, n in self.moves(s)]
            succ_of[s] = ms
            for n in ms:
                if n not in seen and n not in memo:
                    seen.add(n)
                    stack.append(n)
        # 이동마다 진행 위치의 합이 1 늘어나므로 합의 내림차순이 후속 상태를 먼저 처리하는 순서다.
        for s in sorted(order, key=lambda x: -sum(x)):
            if s in memo:
                continue
            if self.finished(s):
                memo[s] = True
            else:
                memo[s] = any(memo[n] for n in succ_of[s])
        return memo[pcs]

    # ------------------------------------------------------------ 스냅샷 모델과의 연결
    def sm_inst(self, pcs) -> Inst:
        """pcs를 모델 명세의 스냅샷으로. 요청은 다음 연산이 ('A', l)인 스레드의 {e_l}."""
        hm = self.held_masks(pcs)
        L = max(self.L, 1)
        alloc = tuple(tuple(1 if hm[t] >> l & 1 else 0 for l in range(L)) for t in range(self.T))
        alts = []
        for t in range(self.T):
            if pcs[t] < self.end[t] and self.progs[t][pcs[t]][0] == "A":
                l = self.progs[t][pcs[t]][1]
                alts.append(frozenset({tuple(1 if r == l else 0 for r in range(L))}))
            else:
                alts.append(frozenset())
        return Inst(cap=(1,) * L, alloc=alloc, alts=tuple(alts))

    def has_deadlock_set(self, pcs) -> bool:
        pcs = tuple(pcs)
        if pcs not in self._dead:
            self._dead[pcs] = sm.has_deadlock(self.sm_inst(pcs))
        return self._dead[pcs]

    def reachable(self, pcs):
        """pcs에서 도달 가능한 모든 상태(자기 자신 포함)."""
        pcs = tuple(pcs)
        out = {pcs}
        stack = [pcs]
        while stack:
            s = stack.pop()
            for _, n in self.moves(s):
                if n not in out:
                    out.add(n)
                    stack.append(n)
        return out

    def possible_deadlock(self, pcs) -> bool:
        pcs = tuple(pcs)
        if pcs in self._reach:
            return self._reach[pcs]
        res = any(self.has_deadlock_set(s) for s in self.reachable(pcs))
        self._reach[pcs] = res
        return res

    # ------------------------------------------------------------ M1의 구성 요소
    def next_op(self, pcs, t):
        return self.progs[t][pcs[t]] if pcs[t] < self.end[t] else None

    def request_permissible(self, pcs, t) -> bool:
        """스레드 t의 다음 연산이 ('A', l)일 때의 오라클 허용 가능(prereg/RQ3.md §5 M1)."""
        op = self.next_op(pcs, t)
        if op is None or op[0] != "A":
            raise ValueError("다음 연산이 락 요청이 아님")
        l = op[1]
        hm = self.held_masks(pcs)
        others = 0
        for u in range(self.T):
            if u != t:
                others |= hm[u]
        if others >> l & 1:
            return self.safe(pcs)
        return self.safe(pcs[:t] + (pcs[t] + 1,) + pcs[t + 1:])

    def all_states(self):
        """위치 곱 공간의 모든 상태 중 쥔 락이 겹치지 않는 것."""
        import itertools
        for pcs in itertools.product(*[range(e + 1) for e in self.end]):
            if self.valid_state(pcs):
                yield pcs

    def reachable_from_start(self):
        return self.reachable(tuple(0 for _ in range(self.T)))


# ---------------------------------------------------------------- 독립 구현(교차 검증용)

def safe_bruteforce(progs, pcs) -> bool:
    """메모 없는 완전 탐색. LockProgSystem.safe와 코드 경로가 다르다(비트마스크 대신 집합과 재귀)."""
    progs = [list(p) for p in progs]
    T = len(progs)

    def held_by(pcs_, u):
        h = set()
        for k, l in progs[u][:pcs_[u]]:
            if k == "A":
                h.add(l)
            else:
                h.discard(l)
        return h

    def rec(pcs_):
        if all(pcs_[u] == len(progs[u]) for u in range(T)):
            return True
        for t in range(T):
            if pcs_[t] == len(progs[t]):
                continue
            k, l = progs[t][pcs_[t]]
            if k == "A" and any(l in held_by(pcs_, u) for u in range(T) if u != t):
                continue
            nxt = list(pcs_)
            nxt[t] += 1
            if rec(tuple(nxt)):
                return True
        return False

    return rec(tuple(pcs))


def deadlock_set_bruteforce(progs, pcs) -> bool:
    """상태 pcs에 교착 집합이 있는가를 정의대로 구한다(가장 큰 고정점). SM 오라클과 다른 코드 경로다.

    교착 집합 U: U의 모든 스레드의 다음 연산이 ('A', l)이고 l을 U의 다른 스레드가 쥐고 있다
    (자기 자신이 쥔 락을 다시 얻는 경우는 valid_program이 금한다).
    """
    progs = [list(p) for p in progs]
    T = len(progs)

    def held_by(u):
        h = set()
        for k, l in progs[u][:pcs[u]]:
            if k == "A":
                h.add(l)
            else:
                h.discard(l)
        return h

    cand = {t for t in range(T)
            if pcs[t] < len(progs[t]) and progs[t][pcs[t]][0] == "A"}
    changed = True
    while changed:
        changed = False
        for t in sorted(cand):
            l = progs[t][pcs[t]][1]
            if not any(u != t and l in held_by(u) for u in cand):
                cand.discard(t)
                changed = True
    return bool(cand)


def possible_deadlock_bruteforce(progs, pcs) -> bool:
    """도달 가능한 상태 중 교착 집합이 있는 것이 있는가(완전 탐색)."""
    progs = [list(p) for p in progs]
    T = len(progs)

    def held_by(pcs_, u):
        h = set()
        for k, l in progs[u][:pcs_[u]]:
            if k == "A":
                h.add(l)
            else:
                h.discard(l)
        return h

    seen = set()
    stack = [tuple(pcs)]
    while stack:
        s = stack.pop()
        if s in seen:
            continue
        seen.add(s)
        if deadlock_set_bruteforce(progs, s):
            return True
        for t in range(T):
            if s[t] == len(progs[t]):
                continue
            k, l = progs[t][s[t]]
            if k == "A" and any(l in held_by(s, u) for u in range(T) if u != t):
                continue
            nxt = list(s)
            nxt[t] += 1
            stack.append(tuple(nxt))
    return False


def program(order, release="nested"):
    """락 번호 열 order(획득 순서)에서 프로그램을 만든다.

    release: 'nested'  획득의 역순으로 반납(LIFO)
             'fifo'    획득 순서대로 반납
             'hoh'     손잡기(hand-over-hand): A1 A2 R1 A3 R2 ... Ak R(k-1) Rk
    """
    order = tuple(order)
    k = len(order)
    ops = []
    if release == "nested":
        ops = [("A", l) for l in order] + [("R", l) for l in reversed(order)]
    elif release == "fifo":
        ops = [("A", l) for l in order] + [("R", l) for l in order]
    elif release == "hoh":
        if k < 2:
            ops = [("A", order[0]), ("R", order[0])] if k == 1 else []
        else:
            ops = [("A", order[0]), ("A", order[1])]
            for i in range(2, k):
                ops += [("R", order[i - 2]), ("A", order[i])]
            ops += [("R", order[k - 2]), ("R", order[k - 1])]
    else:
        raise ValueError(release)
    return tuple(ops)


def show(progs, pcs=None) -> str:
    rows = []
    for t, p in enumerate(progs):
        s = " ".join(f"{k}{l}" for k, l in p)
        mark = f"  pc={pcs[t]}" if pcs is not None else ""
        rows.append(f"T{t}: {s}{mark}")
    return "\n".join(rows)
