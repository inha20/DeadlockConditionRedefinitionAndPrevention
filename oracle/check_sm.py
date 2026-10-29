#!/usr/bin/env python3
"""SM 정리의 소규모 전수 검증.

사용법: python3 -I check_sm.py [결과를 쓸 마크다운 경로]

문서 spec/model-spec.md §6의 정리 진술을 작은 모델에서 모든 상태를 열거해 검사한다.
이것은 정리의 증명이 아니라 반례 탐색이다. 통과한 범위(프로세스 수, 자원 종류 수, 용량)를 결과에 함께 적는다.
"""
from __future__ import annotations

import collections
import itertools
import os
import sys
import time

# -I(격리 모드)로 실행해도 같은 폴더의 sm.py를 찾도록 이 파일의 폴더를 경로에 넣는다.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sm  # noqa: E402
from sm import Inst  # noqa: E402


def alloc_mats(n, cap):
    per_res = [[v for v in itertools.product(range(c + 1), repeat=n) if sum(v) <= c] for c in cap]
    for combo in itertools.product(*per_res):
        yield tuple(tuple(combo[r][p] for r in range(len(cap))) for p in range(n))


def nonzero_vecs(cap):
    return [v for v in itertools.product(*[range(c + 1) for c in cap]) if any(v)]


def e(m, r):
    return tuple(1 if i == r else 0 for i in range(m))


def opts_and1(cap):
    m = len(cap)
    return [frozenset()] + [frozenset({tuple(1 if (mask >> r) & 1 else 0 for r in range(m))}) for mask in range(1, 1 << m)]


def opts_or1(cap):
    m = len(cap)
    return [frozenset()] + [frozenset(e(m, r) for r in range(m) if (mask >> r) & 1) for mask in range(1, 1 << m)]


def opts_single(cap):
    m = len(cap)
    return [frozenset()] + [frozenset({e(m, r)}) for r in range(m)]


def opts_vec(cap):
    return [frozenset()] + [frozenset({v}) for v in nonzero_vecs(cap)]


def opts_dnf(cap, k=2):
    vs = nonzero_vecs(cap)
    out = [frozenset()]
    for size in range(1, k + 1):
        out += [frozenset(c) for c in itertools.combinations(vs, size)]
    return out


def fd_holds(inst: Inst) -> bool:
    """실현 가능한 총수요(FD): 어느 대안도 이미 쥔 양을 더해 용량을 넘지 않는다."""
    return all(all(inst.alloc[p][r] + a[r] <= inst.cap[r] for r in range(inst.m))
               for p in range(inst.n) for a in inst.alts[p])


def ordered(inst: Inst) -> bool:
    """자원 종류 번호 순서 규칙: 요청하는 모든 자원의 번호가 이미 쥔 모든 자원의 번호보다 크다."""
    for p in range(inst.n):
        held = [r for r in range(inst.m) if inst.alloc[p][r] > 0]
        for a in inst.alts[p]:
            for r in range(inst.m):
                if a[r] > 0 and any(h >= r for h in held):
                    return False
    return True


def completable_by_permutation(inst: Inst) -> bool:
    """모든 프로세스를 어떤 순서로 하나씩 끝낼 수 있는가. 순열을 전부 시도한다(축소와 독립인 구현).
    p의 요청이 지금까지 돌려받은 자원을 합친 F로 만족되면 p는 끝나고 보유량을 돌려준다."""
    base = sm.free(inst)
    for perm in itertools.permutations(range(inst.n)):
        F = list(base)
        ok = True
        for p in perm:
            if not sm.sat(inst.alts[p], tuple(F)):
                ok = False
                break
            for r in range(inst.m):
                F[r] += inst.alloc[p][r]
        if ok:
            return True
    return False


def all_at_once(inst: Inst) -> bool:
    """대기 중인 프로세스는 아무것도 쥐고 있지 않다(점유-대기 제거)."""
    return all((not inst.alts[p]) or sum(inst.alloc[p]) == 0 for p in range(inst.n))


# 각 검사는 True(성립), False(위반), None(해당 없음)을 돌려준다.
def make_checks(cap_is_one: bool):
    def L1(i, ctx):  # 교착 집합의 합집합은 교착 집합이다
        s = ctx["sets"]
        return all(sm.is_deadlock_set(i, a | b) for a, b in itertools.combinations(s, 2))

    def L2(i, ctx):  # 축소 결과 = 가장 큰 교착 집합
        s = ctx["sets"]
        union = frozenset().union(*s) if s else frozenset()
        return sm.greatest_deadlock_set(i) == union

    def L3(i, ctx):  # 순열 전수 탐색으로 전원이 끝날 수 있음 <=> 교착 집합이 없음
        return completable_by_permutation(i) == (not ctx["sets"])

    def T1a(i, ctx):  # 극소 교착 집합의 모든 구성원은 단위를 쥔다
        return all(all(sum(i.alloc[p]) > 0 for p in U) for U in ctx["mins"])

    def T1b(i, ctx):  # 극소 교착 집합의 의존 그래프는 강연결(크기 1이면 자기 간선)
        for U in ctx["mins"]:
            adj = sm.dep_graph(i, U)
            if not sm.strongly_connected(adj):
                return False
            if len(U) == 1 and not sm.has_cycle(adj, True):
                return False
        return True

    def T1c(i, ctx):  # FD이면 크기 1인 교착 집합이 없다
        if not fd_holds(i):
            return None
        return all(len(U) >= 2 for U in ctx["sets"])

    def T1d(i, ctx):  # FD이면 극소 교착 집합에 길이 2 이상의 순환이 있다
        if not fd_holds(i):
            return None
        return all(sm.has_cycle(sm.dep_graph(i, U), allow_self_loop=False) for U in ctx["mins"])

    def T2(i, ctx):  # 용량 1, AND: 교착 <=> 대기 그래프 순환
        return bool(ctx["sets"]) == sm.has_cycle(sm.wait_for_graph(i), True)

    def T34(i, ctx):  # expedient: 교착 <=> 매듭
        if not sm.expedient(i):
            return None
        return bool(ctx["sets"]) == sm.rag_knot_exists(i)

    def T5a(i, ctx):  # expedient: 매듭 => 교착
        if not sm.expedient(i):
            return None
        return (not sm.rag_knot_exists(i)) or bool(ctx["sets"])

    def T2n(i, ctx):  # 교착이면 대기 그래프에 순환(자기 간선 포함)이 있다(필요조건, 모든 용량)
        if not ctx["sets"]:
            return None
        return sm.has_cycle(sm.wait_for_graph(i), True)

    def T3i(i, ctx):  # 단일 단위 대안으로만 된 요청: 교착이면 expedient 여부와 무관하게 매듭이 있다
        if not ctx["sets"]:
            return None
        return sm.rag_knot_exists(i)

    def T5c(i, ctx):  # 교착이면 자원 할당 그래프에 순환이 있다(필요조건)
        if not ctx["sets"]:
            return None
        return sm.rag_has_cycle(i)

    def T8(i, ctx):  # 타임스탬프 불변식(프로세스 번호가 나이): FD이고 다른 프로세스를 기다리는 간선이 모두 같은 방향이면 교착 없음
        if not fd_holds(i):
            return None
        adj = sm.wait_for_graph(i)
        edges = [(p, q) for p in adj for q in adj[p] if p != q]
        if not (all(p < q for p, q in edges) or all(p > q for p, q in edges)):
            return None
        return not ctx["sets"]

    def T6(i, ctx):  # 순서 규칙을 지키는 상태에는 교착이 없다
        if not ordered(i):
            return None
        return not ctx["sets"]

    def T7(i, ctx):  # 대기 중 아무것도 쥐지 않으면 교착이 없다
        if not all_at_once(i):
            return None
        return not ctx["sets"]

    return {"L1": L1, "L2": L2, "L3": L3, "T1a": T1a, "T1b": T1b, "T1c": T1c, "T1d": T1d,
            "T2": T2, "T2n": T2n, "T3": T34, "T3i": T3i, "T5a": T5a, "T5c": T5c,
            "T6": T6, "T7": T7, "T8": T8}


# 반례가 있을 것으로 예상하는 진술. 같은 종류도 FD(자기 대기 없음)를 만족하는 예와 아닌 예를 따로 모은다.
def expected_failures(i, ctx):
    out = []
    exp = sm.expedient(i)
    dl = bool(ctx["sets"])
    knot = sm.rag_knot_exists(i)
    cyc = sm.rag_has_cycle(i)
    if exp and dl and not knot:
        out.append("교착이지만 매듭 없음(매듭은 필요조건이 아님)")
    if cyc and not dl:
        out.append("RAG에 순환이 있으나 교착 아님(순환은 충분조건이 아님)")
    if exp and cyc and not dl:
        out.append("expedient이고 RAG에 순환이 있으나 교착 아님")
    if (exp and all(len(a) <= 1 for a in i.alts) and any(c > 1 for c in i.cap)
            and sm.has_cycle(sm.wait_for_graph(i), allow_self_loop=False) and not dl):
        out.append("expedient이고 AND 요청이며 다중 단위 자원이 있을 때 대기 그래프에 길이 2 이상 순환이 있으나 교착 아님")
    return out


FAMILIES = [
    # 이름, 용량, 프로세스 수, 요청 옵션 생성기, 적용할 검사 이름들
    ("AND·용량1·m=3·n=3", (1, 1, 1), 3, opts_and1, ["L1", "L2", "L3", "T1a", "T1b", "T1c", "T1d", "T2", "T2n", "T5a", "T5c", "T6", "T7", "T8"]),
    ("AND·용량1·m=2·n=4", (1, 1), 4, opts_and1, ["L1", "L2", "L3", "T1a", "T1b", "T1c", "T1d", "T2", "T2n", "T5a", "T5c", "T6", "T7", "T8"]),
    ("OR·용량1·m=3·n=3", (1, 1, 1), 3, opts_or1, ["L1", "L2", "L3", "T1a", "T1b", "T1c", "T1d", "T2n", "T3", "T3i", "T5a", "T5c", "T6", "T7", "T8"]),
    ("OR·용량1·m=2·n=4", (1, 1), 4, opts_or1, ["L1", "L2", "L3", "T1a", "T1b", "T1c", "T1d", "T2n", "T3", "T3i", "T5a", "T5c", "T6", "T7", "T8"]),
    ("OR·용량(2,2)·n=3", (2, 2), 3, opts_or1, ["L1", "L2", "L3", "T1a", "T1b", "T1c", "T1d", "T2n", "T3", "T3i", "T5a", "T5c", "T6", "T7", "T8"]),
    ("OR·용량(2,1,2)·n=3", (2, 1, 2), 3, opts_or1, ["L1", "L2", "L3", "T1a", "T1b", "T1c", "T1d", "T2n", "T3", "T3i", "T5a", "T5c", "T6", "T7", "T8"]),
    ("단일단위요청·용량(3,2)·n=3", (3, 2), 3, opts_single, ["L1", "L2", "L3", "T1a", "T1b", "T1c", "T1d", "T2n", "T3", "T3i", "T5a", "T5c", "T6", "T7", "T8"]),
    ("단일단위요청·용량(2,2,2)·n=3", (2, 2, 2), 3, opts_single, ["L1", "L2", "L3", "T1a", "T1b", "T1c", "T1d", "T2n", "T3", "T3i", "T5a", "T5c", "T6", "T7", "T8"]),
    ("벡터 AND·용량(2,2)·n=3", (2, 2), 3, opts_vec, ["L1", "L2", "L3", "T1a", "T1b", "T1c", "T1d", "T2n", "T5a", "T5c", "T6", "T7", "T8"]),
    ("DNF(대안 2개)·용량(2,1)·n=3", (2, 1), 3, lambda c: opts_dnf(c, 2), ["L1", "L2", "L3", "T1a", "T1b", "T1c", "T1d", "T2n", "T5a", "T5c", "T6", "T7", "T8"]),
]


def run_family(name, cap, n, optgen, names):
    checks = make_checks(all(c == 1 for c in cap))
    opts = optgen(cap)
    m = len(cap)
    total = 0
    applic = collections.Counter()
    viol = collections.Counter()
    example = {}
    found = {}
    for alloc in alloc_mats(n, cap):
        per_proc = [opts for _ in range(n)]
        for reqs in itertools.product(*per_proc):
            inst = Inst(cap, alloc, tuple(reqs))
            total += 1
            sets = sm.all_deadlock_sets(inst)
            mins = [U for U in sets if not any(V < U for V in sets)]
            ctx = {"sets": sets, "mins": mins}
            for cn in names:
                r = checks[cn](inst, ctx)
                if r is None:
                    continue
                applic[cn] += 1
                if r is False:
                    viol[cn] += 1
                    example.setdefault(cn, inst)
            fd = fd_holds(inst)
            for k in expected_failures(inst, ctx):
                found.setdefault((k, fd), inst)
    return total, applic, viol, example, found


def main(out_path=None):
    t0 = time.time()
    lines = []
    lines.append("# SM 정리 소규모 전수 검증 결과\n")
    lines.append("`oracle/check_sm.py`가 생성했다. 정리의 증명이 아니라 주어진 범위 안의 전수 검사다.\n")
    lines.append("| 범위 | 상태 수 | 검사 | 적용 상태 수 | 위반 |")
    lines.append("|---|---|---|---|---|")
    all_found = {}
    any_violation = False
    grand_total = 0
    for name, cap, n, optgen, names in FAMILIES:
        total, applic, viol, example, found = run_family(name, cap, n, optgen, names)
        grand_total += total
        for cn in names:
            v = viol.get(cn, 0)
            any_violation |= v > 0
            lines.append(f"| {name} | {total} | {cn} | {applic.get(cn, 0)} | {v} |")
        for cn, inst in example.items():
            lines.append(f"|  | 위반 예시 | {cn} | {sm.show(inst)} |  |")
        for key, inst in found.items():
            all_found.setdefault(key, (name, inst))
        print(f"[{time.time() - t0:6.1f}s] {name}: {total}개 상태, 위반 {dict(viol)}", flush=True)
    lines.append("")
    lines.append("## 반례가 있을 것으로 예상한 진술(예시)\n")
    lines.append("각 진술이 일반적으로는 성립하지 않음을 보이는 가장 먼저 발견된 상태다. FD는 자기 대기(이미 쥔 양을 더하면 용량을 넘는 대안)가 없다는 조건이다.\n")
    kinds = []
    for (k, fd) in all_found:
        if k not in kinds:
            kinds.append(k)
    for k in kinds:
        for fd, label in ((True, "FD 만족(자기 대기 없음)"), (False, "FD 위반(자기 대기 포함)")):
            if (k, fd) in all_found:
                name, inst = all_found[(k, fd)]
                lines.append(f"- {k} — {label}, {name} 범위: `{sm.show(inst)}`")
    if not kinds:
        lines.append("- 예상한 반례를 이 범위에서 찾지 못했다.")
    lines.append("")
    lines.append("검사 이름(문서 spec/model-spec.md §6의 진술과 같은 이름):")
    lines.append("")
    for k, v in [
        ("L1", "교착 집합의 합집합은 교착 집합이다"),
        ("L2", "축소의 잔여 = 가장 큰 교착 집합"),
        ("L3", "순열 전수 탐색으로 전원이 끝날 수 있음 ⟺ 교착 집합이 없음"),
        ("T1a", "극소 교착 집합의 모든 구성원이 단위를 쥔다"),
        ("T1b", "극소 교착 집합의 의존 그래프가 강연결이다(크기 1이면 자기 간선)"),
        ("T1c", "FD이면 크기 1인 교착 집합이 없다"),
        ("T1d", "FD이면 극소 교착 집합의 의존 그래프에 길이 2 이상의 순환이 있다"),
        ("T2", "용량 1, AND: 교착 ⟺ 대기 그래프 순환(자기 간선 포함)"),
        ("T2n", "교착이면 대기 그래프에 순환이 있다"),
        ("T3", "단일 단위 대안: expedient 상태에서 교착 ⟺ 자원 할당 그래프의 매듭"),
        ("T3i", "단일 단위 대안: 교착이면 매듭이 있다(expedient 불필요)"),
        ("T5a", "expedient이고 매듭이 있으면 교착이다"),
        ("T5c", "교착이면 자원 할당 그래프에 순환이 있다"),
        ("T6", "순서 불변식(ORD)이면 교착 집합이 없다"),
        ("T7", "대기 중 아무것도 쥐지 않으면(ALL) 교착 집합이 없다"),
        ("T8", "FD이고 대기 간선이 모두 같은 방향이면(타임스탬프 불변식) 교착 집합이 없다"),
    ]:
        lines.append(f"- {k}: {v}")
    lines.append(f"\n합계 {grand_total}개 상태(범위 {len(FAMILIES)}개), 총 소요 {time.time() - t0:.0f}초.")
    text = "\n".join(lines) + "\n"
    if out_path:
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    print("위반 있음" if any_violation else "모든 검사 통과")
    return 1 if any_violation else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
