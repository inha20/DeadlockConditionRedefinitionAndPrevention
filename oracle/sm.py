"""스냅샷 모델(SM)의 정확 오라클.

문서 spec/model-spec.md의 정의를 그대로 코드로 옮긴 것이다. 성능보다 정의와의 일치를 우선한다.

한 상태(Inst)는 다음으로 이루어진다.
  cap[r]      자원 종류 r의 단위 수(용량)
  alloc[p][r] 프로세스 p가 쥔 r의 단위 수
  alts[p]     p의 대기 중인 요청. 대안(alternative) 벡터의 집합이며 비어 있으면 요청이 없다.
              요청은 "대안 중 하나를 통째로 얻으면 진행"이라는 DNF 형태다.
              단일 단위 요청, AND, OR, AND-OR, P-out-of-Q를 모두 이 형태로 쓸 수 있다.
교착 집합 U(비어 있지 않은 프로세스 집합)는 U의 모든 구성원이 요청을 가지고 있고,
U가 쥔 단위를 아무도 반납하지 않는 가장 유리하지 않은 경우(= 나머지는 모두 반납한다고 가정한
Free_max(U) = cap - A(U))에도 어느 대안도 만족되지 않는 집합이다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

Vec = tuple[int, ...]


@dataclass(frozen=True)
class Inst:
    cap: Vec
    alloc: tuple[Vec, ...]
    alts: tuple[frozenset, ...]

    @property
    def n(self) -> int:
        return len(self.alloc)

    @property
    def m(self) -> int:
        return len(self.cap)


# ---------------------------------------------------------------- 기본 연산

def free(inst: Inst) -> Vec:
    return tuple(inst.cap[r] - sum(a[r] for a in inst.alloc) for r in range(inst.m))


def alloc_of(inst: Inst, procs: Iterable[int]) -> Vec:
    procs = tuple(procs)
    return tuple(sum(inst.alloc[p][r] for p in procs) for r in range(inst.m))


def sat(alts: frozenset, F: Vec) -> bool:
    """요청이 F로 만족되는가. 요청이 없으면(빈 집합) 만족된 것으로 본다(막히지 않음)."""
    if not alts:
        return True
    for alt in alts:
        if all(alt[r] <= F[r] for r in range(len(F))):
            return True
    return False


def waiting(inst: Inst, p: int) -> bool:
    return bool(inst.alts[p])


def expedient(inst: Inst) -> bool:
    """대기 중인 모든 요청이 현재 Free로도 만족되지 않는다(만족 가능한 요청은 이미 허용됨)."""
    F = free(inst)
    return all((not inst.alts[p]) or (not sat(inst.alts[p], F)) for p in range(inst.n))


# ---------------------------------------------------------------- 교착 집합

def is_deadlock_set(inst: Inst, U: Iterable[int]) -> bool:
    U = tuple(U)
    if not U:
        return False
    AU = alloc_of(inst, U)
    Fmax = tuple(inst.cap[r] - AU[r] for r in range(inst.m))
    return all(inst.alts[p] and not sat(inst.alts[p], Fmax) for p in U)


def greatest_deadlock_set(inst: Inst) -> frozenset:
    """축소(reduction)로 구한 교착 집합. 만족 가능한 프로세스를 하나씩 완료시켜 자원을 돌려받는다."""
    F = list(free(inst))
    alive = set(range(inst.n))
    changed = True
    while changed:
        changed = False
        for p in sorted(alive):
            if sat(inst.alts[p], tuple(F)):
                for r in range(inst.m):
                    F[r] += inst.alloc[p][r]
                alive.discard(p)
                changed = True
    return frozenset(alive)


def all_deadlock_sets(inst: Inst) -> list[frozenset]:
    n = inst.n
    out = []
    for mask in range(1, 1 << n):
        U = [p for p in range(n) if mask >> p & 1]
        if is_deadlock_set(inst, U):
            out.append(frozenset(U))
    return out


def minimal_deadlock_sets(inst: Inst) -> list[frozenset]:
    sets = all_deadlock_sets(inst)
    return [U for U in sets if not any(V < U for V in sets)]


def has_deadlock(inst: Inst) -> bool:
    return bool(greatest_deadlock_set(inst))


# ---------------------------------------------------------------- 의존 그래프 D(U)

def dep_graph(inst: Inst, U: Iterable[int]) -> dict[int, set[int]]:
    """p -> q 는 q가 U 안에서 p의 어떤 대안을 막는 자원 단위를 쥐고 있다는 뜻(자기 자신 포함)."""
    U = tuple(U)
    AU = alloc_of(inst, U)
    adj: dict[int, set[int]] = {p: set() for p in U}
    for p in U:
        for alt in inst.alts[p]:
            for r in range(inst.m):
                if alt[r] > inst.cap[r] - AU[r]:
                    for q in U:
                        if inst.alloc[q][r] > 0:
                            adj[p].add(q)
    return adj


def _reach(adj: dict[int, set[int]], s: int) -> set[int]:
    seen = {s}
    stack = [s]
    while stack:
        x = stack.pop()
        for y in adj.get(x, ()):
            if y not in seen:
                seen.add(y)
                stack.append(y)
    return seen


def strongly_connected(adj: dict[int, set[int]]) -> bool:
    nodes = list(adj)
    return all(set(nodes) <= _reach(adj, s) for s in nodes)


def has_cycle(adj: dict[int, set[int]], allow_self_loop: bool = True) -> bool:
    """유향 순환이 있는가. allow_self_loop=False이면 길이 2 이상의 순환만 센다."""
    color: dict[int, int] = {}

    def dfs(x: int) -> bool:
        color[x] = 1
        for y in adj.get(x, ()):
            if y == x:
                if allow_self_loop:
                    return True
                continue
            c = color.get(y, 0)
            if c == 1:
                return True
            if c == 0 and dfs(y):
                return True
        color[x] = 2
        return False

    return any(color.get(x, 0) == 0 and dfs(x) for x in list(adj))


# ---------------------------------------------------------------- 대기 그래프와 매듭

def wait_for_graph(inst: Inst) -> dict[int, set[int]]:
    """대기 그래프. p -> q 는 p의 어떤 대안이 요구하는 자원의 단위를 q가 쥐고 있다는 뜻(자기 자신 포함).
    용량 1 자원에서는 현재 Free와 무관하게 '쥔 자가 있으면 간선'이다."""
    adj: dict[int, set[int]] = {p: set() for p in range(inst.n)}
    for p in range(inst.n):
        for alt in inst.alts[p]:
            for r in range(inst.m):
                if alt[r] > 0:
                    for q in range(inst.n):
                        if inst.alloc[q][r] > 0:
                            adj[p].add(q)
    return adj


def _tarjan(nodes: list, succ: dict) -> list[list]:
    index = {}
    low = {}
    onstack = set()
    stack = []
    out = []
    counter = [0]

    def strong(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        onstack.add(v)
        for w in succ.get(v, ()):
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in onstack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                onstack.discard(w)
                comp.append(w)
                if w == v:
                    break
            out.append(comp)

    for v in nodes:
        if v not in index:
            strong(v)
    return out


def rag_knot_exists(inst: Inst) -> bool:
    """자원 할당 그래프(프로세스 노드, 자원 노드)에서 매듭이 있는가.
    요청 간선 p -> r (p의 어떤 대안이 r을 요구), 할당 간선 r -> q (q가 r을 쥠).
    매듭 = 밖으로 나가는 간선이 없는 강연결 성분 중 노드가 2개 이상인 것."""
    nodes = [("p", p) for p in range(inst.n)] + [("r", r) for r in range(inst.m)]
    succ: dict = {v: set() for v in nodes}
    for p in range(inst.n):
        for alt in inst.alts[p]:
            for r in range(inst.m):
                if alt[r] > 0:
                    succ[("p", p)].add(("r", r))
    for q in range(inst.n):
        for r in range(inst.m):
            if inst.alloc[q][r] > 0:
                succ[("r", r)].add(("p", q))
    comps = _tarjan(nodes, succ)
    comp_of = {v: i for i, c in enumerate(comps) for v in c}
    for i, c in enumerate(comps):
        if len(c) < 2:
            continue
        if all(comp_of[w] == i for v in c for w in succ[v]):
            return True
    return False


def rag_has_cycle(inst: Inst) -> bool:
    """자원 할당 그래프에 유향 순환이 있는가."""
    nodes = [("p", p) for p in range(inst.n)] + [("r", r) for r in range(inst.m)]
    succ: dict = {v: set() for v in nodes}
    for p in range(inst.n):
        for alt in inst.alts[p]:
            for r in range(inst.m):
                if alt[r] > 0:
                    succ[("p", p)].add(("r", r))
    for q in range(inst.n):
        for r in range(inst.m):
            if inst.alloc[q][r] > 0:
                succ[("r", r)].add(("p", q))
    comps = _tarjan(nodes, succ)
    return any(len(c) >= 2 for c in comps)


# ---------------------------------------------------------------- 사람이 읽는 표기

def show(inst: Inst) -> str:
    rows = []
    for p in range(inst.n):
        alts = sorted(inst.alts[p])
        rows.append(f"P{p}: 보유{list(inst.alloc[p])} 요청{[list(a) for a in alts] if alts else '-'}")
    return f"용량{list(inst.cap)} Free{list(free(inst))} | " + "; ".join(rows)
