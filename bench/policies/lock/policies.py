"""RQ3의 기준 정책 구현 (AI 초안, 사람 검토 전, 동결 전).

기존 알고리즘의 교재·문헌 서술을 락 프로그램 모델(system.py)에 옮긴 것이다. 의미의 선택(대기열 순서,
락 넘김 시점의 처리, 타임스탬프 유지 등)은 docs/rq3/policies.md에 근거와 함께 적었고 사람이 정한다.
P-INC-F/R(증분 순서 승인)은 동결 전에 구현하지 않는다(문서 02 §3).

정책 코드(prereg/RQ3.md §4.1)
  B0     무정책
  B1     주기적 대기 그래프 탐지 + 희생자 선택(탐지)
  P-ORD  락 클래스 순서화(예방, K2)
  P-ALL  일괄 요청(예방, K1)
  P-RET  반납 후 재시도(트라이락 + 백오프, 예방, K0)
  P-WD   wait-die(예방, K0 + 타임스탬프)
  P-WW   wound-wait(예방, K0 + 타임스탬프)
  P-PCP  우선순위 천장(예방/회피 경계, K2)
  P-BNK  뱅커(회피, K1)
  P-RAG  단일 인스턴스 그래프 기반 회피(회피, K1)
  P-MIX  락 그룹 사이는 순서화, 그룹 안은 wound-wait(혼합, K2 + 타임스탬프)
"""
from __future__ import annotations

from .system import (D_DENY, D_FAIL, D_GRANT, D_WAIT, BLOCKED, LockTable, Policy, RUN, wound)


# ---------------------------------------------------------------- 공용 도구

def _mask(locks) -> int:
    m = 0
    for l in locks:
        m |= 1 << l
    return m


def find_cycle(adj: dict):
    """유향 그래프 adj(노드 -> 이웃 집합)의 순환 하나(노드 리스트)를 돌려준다. 없으면 None. 결정적이다."""
    color: dict = {}
    for s in sorted(adj):
        if color.get(s):
            continue
        stack = [(s, iter(sorted(adj.get(s, ()))))]
        path = [s]
        color[s] = 1
        while stack:
            node, it = stack[-1]
            advanced = False
            for nxt in it:
                c = color.get(nxt, 0)
                if c == 0:
                    color[nxt] = 1
                    path.append(nxt)
                    stack.append((nxt, iter(sorted(adj.get(nxt, ())))))
                    advanced = True
                    break
                if c == 1:
                    return path[path.index(nxt):]
            if not advanced:
                color[node] = 2
                path.pop()
                stack.pop()
    return None


def banker_safe(tb: LockTable, grant=None) -> bool:
    """교재식 안전성 알고리즘(비트마스크). grant = (t, 락 집합)이면 그것을 허가한 뒤의 상태를 본다.

    단위 용량 1, 청구 0/1이다. 청구 = 활성 스레드의 작업이 쓸 락 집합(선언). need = 청구 - 쥔 것.
    """
    T = tb.T
    alloc = [_mask(tb.held_of(u)) for u in range(T)]
    claim = [_mask(tb.claim(u)) for u in range(T)]
    free = _mask(l for l in range(tb.L) if tb.holder[l] is None)
    if grant is not None:
        t, locks = grant
        m = _mask(locks)
        alloc[t] |= m
        free &= ~m
        claim[t] |= m                       # 허가한 락은 청구에 들어 있어야 한다(선언 위반 방지)
    need = [claim[u] & ~alloc[u] for u in range(T)]
    work = free
    alive = [u for u in range(T) if claim[u] or alloc[u]]
    changed = True
    while changed and alive:
        changed = False
        rest = []
        for u in alive:
            if need[u] & ~work == 0:
                work |= alloc[u]
                changed = True
            else:
                rest.append(u)
        alive = rest
    return not alive


def claim_wait_cycle(tb: LockTable, grant=None):
    """청구 대기 그래프의 순환. u -> w는 u의 남은 청구에 w가 쥔 락이 있다는 뜻(교재의 청구 간선 포함 RAG)."""
    holder = list(tb.holder)
    claim = [set(tb.claim(u)) for u in range(tb.T)]
    if grant is not None:
        t, locks = grant
        for l in locks:
            holder[l] = t
            claim[t].add(l)
    adj = {u: set() for u in range(tb.T)}
    for u in range(tb.T):
        for l in claim[u]:
            w = holder[l]
            if w is not None and w != u:
                adj[u].add(w)
    return find_cycle(adj)


# ---------------------------------------------------------------- 기준선

class B0(Policy):
    name = "B0"
    info = "K0"
    kind = "none"


class B1(Policy):
    """대기 그래프 탐지. 탐지 시점은 하네스가 정한다(소규모 전수 검사에서는 언제든 가능한 동작).

    희생자: 순환에 속한 스레드 중 타임스탬프가 가장 큰(가장 젊은) 하나. 순환이 여럿이면 결정적으로 첫 순환.
    """
    name = "B1"
    info = "K0"
    kind = "detection"
    detects = True

    def detect(self, tb):
        adj = {t: set() for t in tb.blocked}
        for t, u in tb.wfg_edges():
            adj[t].add(u)
        cyc = find_cycle({t: {u for u in adj[t] if u in adj} for t in adj})
        if not cyc:
            return ()
        return (max(cyc, key=lambda t: tb.ts[t]),)


# ---------------------------------------------------------------- 예방

class POrd(Policy):
    name = "P-ORD"
    info = "K2"
    kind = "prevention"

    def request(self, tb, t, l):
        held = tb.held_of(t)
        if held and l <= max(held):
            return D_FAIL                    # 결정적 순서 위반: 재시도해도 같은 결과
        return super().request(tb, t, l)

    def invariant(self, tb):
        for t in tb.blocked:
            if tb.bkind[t] != "op":
                continue
            (l,) = tuple(tb.want[t])
            for h in tb.held_of(t):
                if not h < l:
                    return f"ORD 위반: 스레드 {t}가 락 {h}를 쥔 채 락 {l}을 기다림"
        return None


class PAll(Policy):
    name = "P-ALL"
    info = "K1"
    kind = "prevention"
    batch = True

    def begin(self, tb, t):
        want = tb.claim_all[t]
        if not want:
            return
        if all(tb.holder[l] is None for l in want):
            for l in want:
                tb.holder[l] = t
        else:
            tb.block(t, want, kind="begin")

    def invariant(self, tb):
        for t in tb.blocked:
            if tb.held_of(t):
                return f"ALL 위반: 스레드 {t}가 락 {sorted(tb.held_of(t))}를 쥔 채 대기"
        return None


class PRet(Policy):
    name = "P-RET"
    info = "K0"
    kind = "prevention"

    def request(self, tb, t, l):
        if not tb.held_of(t):
            return super().request(tb, t, l)  # 아무것도 쥐지 않았으면 기다려도 된다
        return D_GRANT if tb.holder[l] is None else D_DENY   # 트라이락: 실패하면 모두 반납하고 재시작

    def invariant(self, tb):
        for t in tb.blocked:
            if tb.held_of(t):
                return f"RET 위반: 스레드 {t}가 락 {sorted(tb.held_of(t))}를 쥔 채 대기"
        return None


class PWD(Policy):
    """wait-die. 나이 많은 요청자는 기다리고 젊은 요청자는 죽는다(자기 중단, 같은 타임스탬프로 재시작).

    대기열은 젊은 쪽이 먼저다(키 = -ts). 락을 넘길 때 나머지 대기자는 모두 새 보유자보다 나이가 많아
    '나이 많은 쪽이 젊은 쪽을 기다린다'는 불변식이 유지된다.
    """
    name = "P-WD"
    info = "K0+ts"
    kind = "prevention"
    oldest_safe = True        # 끝나지 않은 스레드 중 가장 나이 많은 스레드는 중단되지 않아야 한다(점검 대상)

    def key(self, tb, t, l):
        return -tb.ts[t]

    def request(self, tb, t, l):
        h = tb.holder[l]
        if h is None:
            return D_GRANT
        return D_WAIT if tb.ts[t] < tb.ts[h] else D_DENY

    def invariant(self, tb):
        for t, u in tb.wfg_edges():
            if not tb.ts[t] < tb.ts[u]:
                return f"WD 위반: 스레드 {t}(ts {tb.ts[t]})가 더 나이 많은 스레드 {u}(ts {tb.ts[u]})를 기다림"
        return None


class PWW(Policy):
    """wound-wait. 나이 많은 요청자는 젊은 보유자를 중단시키고(wound) 젊은 요청자는 기다린다.

    피해자는 쥔 락을 모두 반납하고 같은 타임스탬프로 재시작한다. 대기열은 나이 많은 쪽이 먼저다(키 = ts).
    """
    name = "P-WW"
    info = "K0+ts"
    kind = "prevention"
    oldest_safe = True

    def key(self, tb, t, l):
        return tb.ts[t]

    def request(self, tb, t, l):
        h = tb.holder[l]
        if h is None:
            return D_GRANT
        return wound(h) if tb.ts[t] < tb.ts[h] else D_WAIT

    def invariant(self, tb):
        for t, u in tb.wfg_edges():
            if not tb.ts[t] > tb.ts[u]:
                return f"WW 위반: 스레드 {t}(ts {tb.ts[t]})가 더 젊은 스레드 {u}(ts {tb.ts[u]})를 기다림"
        return None


class PPCP(Policy):
    """우선순위 천장. 락 l의 천장 = l을 쓰는 스레드의 최대 우선순위(K2).

    스레드 t의 요청은 prio[t]가 '다른 스레드가 쥔 락의 천장 최댓값(시스템 천장)'보다 클 때만 허가한다.
    이 규칙만 옮겼고 우선순위 상속은 스케줄러의 몫이라 넣지 않았다(논리 시간 시뮬레이션에 스케줄러가 없음).
    """
    name = "P-PCP"
    info = "K2"
    kind = "prevention/avoidance"

    def key(self, tb, t, l):
        return -tb.prio[t]

    @staticmethod
    def system_ceiling(tb, t):
        c = -1
        for l in range(tb.L):
            h = tb.holder[l]
            if h is not None and h != t:
                c = max(c, tb.ceiling(l))
        return c

    def admissible(self, tb, t, want):
        return tb.prio[t] > self.system_ceiling(tb, t)

    def invariant(self, tb):
        holders = [u for u in range(tb.T) if tb.held_of(u)]
        for p in holders:
            for q in holders:
                if p < q:
                    p_blocks_q = any(tb.ceiling(x) >= tb.prio[q] for x in tb.held_of(p))
                    q_blocks_p = any(tb.ceiling(x) >= tb.prio[p] for x in tb.held_of(q))
                    if p_blocks_q and q_blocks_p:
                        return f"PCP 위반: 스레드 {p}와 {q}가 서로를 천장으로 막을 수 있는 락을 쥠"
        return None


class PMix(Policy):
    """혼합: 락을 그룹(l // group_size)으로 묶는다. 그룹 사이는 오름차순만 허용(P-ORD), 이미 쥔 최고
    그룹과 같은 그룹 안의 충돌은 wound-wait로 푼다. 더 낮은 그룹을 요청하면 작업 실패(P-ORD와 같다).
    대기열은 나이 많은 쪽이 먼저다."""
    name = "P-MIX"
    info = "K2+ts"
    kind = "prevention"
    oldest_safe = True

    def __init__(self, group_size: int = 2):
        self.g = group_size

    def group(self, l):
        return l // self.g

    def key(self, tb, t, l):
        return tb.ts[t]

    def _gmax(self, tb, t):
        held = tb.held_of(t)
        return max((self.group(x) for x in held), default=None)

    def request(self, tb, t, l):
        gl = self.group(l)
        gmax = self._gmax(tb, t)
        if gmax is not None and gl < gmax:
            return D_FAIL
        h = tb.holder[l]
        if h is None:
            return D_GRANT
        if gmax is not None and gl == gmax and tb.ts[t] < tb.ts[h]:
            return wound(h)
        return D_WAIT

    def invariant(self, tb):
        for t in tb.blocked:
            if tb.bkind[t] != "op":
                continue
            (l,) = tuple(tb.want[t])
            gmax = self._gmax(tb, t)
            q = tb.holder[l]
            if gmax is None or q is None or q == t:
                continue
            if self.group(l) < gmax:
                return f"MIX 위반: 스레드 {t}가 더 낮은 그룹의 락 {l}을 기다림"
            if self.group(l) == gmax and not tb.ts[t] > tb.ts[q]:
                return f"MIX 위반: 같은 그룹 안에서 스레드 {t}(ts {tb.ts[t]})가 더 젊은 {q}(ts {tb.ts[q]})를 기다림"
        return None


# ---------------------------------------------------------------- 회피

class PBnk(Policy):
    name = "P-BNK"
    info = "K1"
    kind = "avoidance"
    audit_o1 = True           # 허가 결정을 정확 오라클 O1과 대조한다(점검 대상)

    def admissible(self, tb, t, want):
        return banker_safe(tb, grant=(t, want))

    def invariant(self, tb):
        return None if banker_safe(tb) else "BNK 위반: 불안전 상태에 도달"


class PRag(Policy):
    name = "P-RAG"
    info = "K1"
    kind = "avoidance"
    audit_o1 = True
    audit_vs_bnk = True       # 단위 용량·0/1 청구에서 P-BNK와 결정이 같아야 한다(점검 대상)

    def admissible(self, tb, t, want):
        return claim_wait_cycle(tb, grant=(t, want)) is None

    def invariant(self, tb):
        return None if claim_wait_cycle(tb) is None else "RAG 위반: 청구 간선을 포함한 순환이 있음"


POLICIES = {
    "B0": B0, "B1": B1, "P-ORD": POrd, "P-ALL": PAll, "P-RET": PRet, "P-WD": PWD, "P-WW": PWW,
    "P-PCP": PPCP, "P-BNK": PBnk, "P-RAG": PRag, "P-MIX": PMix,
}
# 예방·회피 정책(소규모 전수 검사에서 교착이 없어야 하는 것). 탐지(B1)와 기준선(B0)은 제외한다.
GUARANTEED = ("P-ORD", "P-ALL", "P-RET", "P-WD", "P-WW", "P-PCP", "P-BNK", "P-RAG", "P-MIX")


def make(name: str) -> Policy:
    return POLICIES[name]()
