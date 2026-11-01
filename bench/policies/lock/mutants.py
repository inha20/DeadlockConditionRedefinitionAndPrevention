"""점검용으로 일부러 틀린 락 정책 (검사 모음이 이를 잡는지 보려는 것이다. 결과 분석에는 쓰지 않는다).

각 변이체는 기준 정책에서 하나만 바꿨다. 소규모 전수 검사(bench/check_lock_policies.py)가 모두 검출해야 한다.
"""
from __future__ import annotations

from .policies import PAll, PBnk, POrd, PPCP, PRag, PRet, PWD, PWW, PMix, B1, banker_safe, find_cycle
from .system import D_DENY, D_GRANT, D_WAIT, Policy, wound


class MutWDFifo(PWD):
    """wait-die인데 대기열이 도착 순서다(보유자와의 비교만 한다). 락을 넘길 때 나이 순서 불변식이 깨진다."""
    name = "mut:P-WD-fifo"

    def key(self, tb, t, l):
        return None


class MutWWFifo(PWW):
    """wound-wait인데 대기열이 도착 순서다."""
    name = "mut:P-WW-fifo"

    def key(self, tb, t, l):
        return None


class MutWDInverted(PWD):
    """비교 방향이 반대다(젊은 쪽이 기다리고 나이 많은 쪽이 죽는다). 교착은 없지만 가장 나이 많은 작업이 중단된다."""
    name = "mut:P-WD-inverted"

    def key(self, tb, t, l):
        return tb.ts[t]

    def request(self, tb, t, l):
        h = tb.holder[l]
        if h is None:
            return D_GRANT
        return D_WAIT if tb.ts[t] > tb.ts[h] else D_DENY


class MutWWNoWound(PWW):
    """wound-wait에서 나이 많은 요청자도 기다리기만 한다."""
    name = "mut:P-WW-nowound"

    def request(self, tb, t, l):
        return D_GRANT if tb.holder[l] is None else D_WAIT


class MutOrdNoFail(POrd):
    """순서 위반을 검사하지 않는다."""
    name = "mut:P-ORD-nocheck"

    def request(self, tb, t, l):
        return Policy.request(self, tb, t, l)


class MutOrdOffByOne(POrd):
    """바로 앞 락(번호가 하나 작은 락)을 쥔 경우의 위반을 놓친다(경계 오류)."""
    name = "mut:P-ORD-offbyone"

    def request(self, tb, t, l):
        held = tb.held_of(t)
        if held and l < max(held) - 1:
            from .system import D_FAIL
            return D_FAIL
        return Policy.request(self, tb, t, l)


class MutAllPartial(PAll):
    """일괄 요청이 아니라 가능한 만큼 먼저 쥐고 나머지를 기다린다(점유-대기가 남는다)."""
    name = "mut:P-ALL-partial"

    def begin(self, tb, t):
        want = tb.claim_all[t]
        if not want:
            return
        free = [l for l in sorted(want) if tb.holder[l] is None]
        rest = [l for l in sorted(want) if tb.holder[l] is not None]
        for l in free:
            tb.holder[l] = t
        if rest:
            tb.block(t, rest, kind="begin")


class MutRetWaits(PRet):
    """트라이락이 아니라 계속 기다린다."""
    name = "mut:P-RET-waits"

    def request(self, tb, t, l):
        return Policy.request(self, tb, t, l)


class MutPcpGe(PPCP):
    """천장 비교가 >=이다(우선순위가 천장과 같아도 허가)."""
    name = "mut:P-PCP-ge"

    def admissible(self, tb, t, want):
        return tb.prio[t] >= self.system_ceiling(tb, t)


class MutPcpOwn(PPCP):
    """시스템 천장에 자기가 쥔 락도 넣는다. 자기 락의 천장이 높으면 스스로를 막는다(진행이 멈출 수 있다)."""
    name = "mut:P-PCP-own"

    @staticmethod
    def system_ceiling(tb, t):
        c = -1
        for l in range(tb.L):
            if tb.holder[l] is not None:
                c = max(c, tb.ceiling(l))
        return c


class MutBnkNoCheck(PBnk):
    """안전성 검사를 하지 않는다. 락이 비어 있으면 무조건 허가한다(대기열 규율만 남은 무정책과 같다)."""
    name = "mut:P-BNK-nocheck"

    def admissible(self, tb, t, want):
        return True


class MutBnkOneStep(PBnk):
    """허가 뒤 '지금 끝낼 수 있는 스레드가 있는가'만 본다(안전 순서 전체를 보지 않는다)."""
    name = "mut:P-BNK-onestep"

    def admissible(self, tb, t, want):
        from .policies import _mask
        T = tb.T
        alloc = [_mask(tb.held_of(u)) for u in range(T)]
        claim = [_mask(tb.claim(u)) for u in range(T)]
        free = _mask(l for l in range(tb.L) if tb.holder[l] is None)
        m = _mask(want)
        alloc[t] |= m
        free &= ~m
        claim[t] |= m
        need = [claim[u] & ~alloc[u] for u in range(T)]
        live = [u for u in range(T) if claim[u] or alloc[u]]
        return (not live) or any(need[u] & ~free == 0 for u in live)


class MutRagNoClaimEdges(PRag):
    """청구 간선 없이 현재 대기 간선만 본다(허가 뒤 대기 그래프 순환 검사)."""
    name = "mut:P-RAG-noclaim"

    def admissible(self, tb, t, want):
        holder = list(tb.holder)
        for l in want:
            holder[l] = t
        adj = {u: set() for u in range(tb.T)}
        for u in tb.blocked:
            for l in tb.want[u]:
                w = holder[l]
                if w is not None and w != u:
                    adj[u].add(w)
        return find_cycle(adj) is None


class MutMixNoWound(PMix):
    """그룹 안에서도 wound하지 않고 기다리기만 한다."""
    name = "mut:P-MIX-nowound"

    def request(self, tb, t, l):
        gl = self.group(l)
        gmax = self._gmax(tb, t)
        if gmax is not None and gl < gmax:
            from .system import D_FAIL
            return D_FAIL
        return D_GRANT if tb.holder[l] is None else D_WAIT


class MutMixNoOrder(PMix):
    """그룹 사이의 순서 위반을 검사하지 않는다."""
    name = "mut:P-MIX-noorder"

    def request(self, tb, t, l):
        gl = self.group(l)
        gmax = self._gmax(tb, t)
        h = tb.holder[l]
        if h is None:
            return D_GRANT
        if gmax is not None and gl == gmax and tb.ts[t] < tb.ts[h]:
            return wound(h)
        return D_WAIT


class MutB1NoVictim(B1):
    """탐지는 하지만 희생자를 고르지 못한다."""
    name = "mut:B1-novictim"

    def detect(self, tb):
        return ()


class MutB1WrongVictim(B1):
    """희생자를 잘못 고른다. 교착 순환 안의 스레드가 아니라 순환 밖에서 락을 쥐지 않고 기다리는 스레드를 중단하므로
    순환이 풀리지 않는다."""
    name = "mut:B1-wrongvictim"

    def detect(self, tb):
        base = super().detect(tb)
        if not base:
            return ()
        others = [t for t in tb.blocked if t not in base and not tb.held_of(t)]
        return (others[0],) if others else ()


MUTANTS = {
    "P-WD": [MutWDFifo, MutWDInverted],
    "P-WW": [MutWWFifo, MutWWNoWound],
    "P-ORD": [MutOrdNoFail, MutOrdOffByOne],
    "P-ALL": [MutAllPartial],
    "P-RET": [MutRetWaits],
    "P-PCP": [MutPcpGe, MutPcpOwn],
    "P-BNK": [MutBnkNoCheck, MutBnkOneStep],
    "P-RAG": [MutRagNoClaimEdges],
    "P-MIX": [MutMixNoWound, MutMixNoOrder],
    "B1": [MutB1NoVictim, MutB1WrongVictim],
}
