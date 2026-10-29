#!/usr/bin/env python3
"""check_sm.py의 검사가 실제로 오류를 잡는지 보는 변이 시험.

sm.py의 함수를 일부러 틀리게 바꾼 뒤 작은 범위에서 check_sm의 검사를 돌려 위반이 나오는지 본다.
위반이 하나도 나오지 않는 변이는 검사 모음의 사각지대이므로 결과에 그대로 적는다.

사용법: python3 -I mutation_check.py [결과를 쓸 마크다운 경로]
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_sm  # noqa: E402
import sm  # noqa: E402

SMALL = {"AND·용량1·m=2·n=4", "OR·용량1·m=2·n=4", "OR·용량(2,2)·n=3",
         "단일단위요청·용량(3,2)·n=3", "벡터 AND·용량(2,2)·n=3"}


def mut_sat_conservative():
    """요청 성분이 양수일 때 한 단위 더 많이 있어야 만족으로 본다(경계 오류)."""
    orig = sm.sat

    def sat(alts, F):
        if not alts:
            return True
        return any(all(a[r] == 0 or a[r] < F[r] for r in range(len(F))) for a in alts)

    sm.sat = sat
    return lambda: setattr(sm, "sat", orig)


def mut_deadlock_uses_current_free():
    """교착 집합 판정에서 cap - A(U) 대신 현재 free를 쓴다."""
    orig = sm.is_deadlock_set

    def is_deadlock_set(inst, U):
        U = tuple(U)
        if not U:
            return False
        F = sm.free(inst)
        return all(inst.alts[p] and not sm.sat(inst.alts[p], F) for p in U)

    sm.is_deadlock_set = is_deadlock_set
    return lambda: setattr(sm, "is_deadlock_set", orig)


def mut_reduction_one_pass():
    """축소를 한 번만 훑는다(고정점까지 반복하지 않음)."""
    orig = sm.greatest_deadlock_set

    def greatest_deadlock_set(inst):
        F = list(sm.free(inst))
        alive = set(range(inst.n))
        for p in sorted(alive.copy()):
            if sm.sat(inst.alts[p], tuple(F)):
                for r in range(inst.m):
                    F[r] += inst.alloc[p][r]
                alive.discard(p)
        return frozenset(alive)

    sm.greatest_deadlock_set = greatest_deadlock_set
    return lambda: setattr(sm, "greatest_deadlock_set", orig)


def mut_dep_graph_no_self_loop():
    """의존 그래프에서 자기 간선을 뺀다."""
    orig = sm.dep_graph

    def dep_graph(inst, U):
        adj = orig(inst, U)
        for p in adj:
            adj[p].discard(p)
        return adj

    sm.dep_graph = dep_graph
    return lambda: setattr(sm, "dep_graph", orig)


def mut_knot_is_any_cycle():
    """매듭을 '자원 할당 그래프에 순환이 있음'으로 대신한다."""
    orig = sm.rag_knot_exists
    sm.rag_knot_exists = sm.rag_has_cycle
    return lambda: setattr(sm, "rag_knot_exists", orig)


def mut_expedient_always_true():
    """expedient 판정을 항상 참으로 한다."""
    orig = sm.expedient
    sm.expedient = lambda inst: True
    return lambda: setattr(sm, "expedient", orig)


def mut_wfg_skip_free_resources():
    """대기 그래프에서 자유 단위가 남은 종류의 간선을 뺀다."""
    orig = sm.wait_for_graph

    def wait_for_graph(inst):
        F = sm.free(inst)
        adj = {p: set() for p in range(inst.n)}
        for p in range(inst.n):
            for alt in inst.alts[p]:
                for r in range(inst.m):
                    if alt[r] > 0 and F[r] == 0:
                        for q in range(inst.n):
                            if inst.alloc[q][r] > 0:
                                adj[p].add(q)
        return adj

    sm.wait_for_graph = wait_for_graph
    return lambda: setattr(sm, "wait_for_graph", orig)


MUTATIONS = [
    ("sat 경계 오류(한 단위 더 요구)", mut_sat_conservative),
    ("교착 집합 판정에 cap - A(U) 대신 현재 free 사용", mut_deadlock_uses_current_free),
    ("축소를 한 번만 훑음", mut_reduction_one_pass),
    ("의존 그래프에서 자기 간선 제거", mut_dep_graph_no_self_loop),
    ("매듭을 순환으로 대체", mut_knot_is_any_cycle),
    ("expedient를 항상 참으로", mut_expedient_always_true),
    ("대기 그래프에서 자유 단위가 있는 종류의 간선 제거", mut_wfg_skip_free_resources),
]


def main(out_path=None):
    t0 = time.time()
    fams = [f for f in check_sm.FAMILIES if f[0] in SMALL]
    # 변이 전 기준선: 위반이 없어야 한다
    base = set()
    for name, cap, n, optgen, names in fams:
        _, _, viol, _, _ = check_sm.run_family(name, cap, n, optgen, names)
        base |= {k for k, v in viol.items() if v}
    lines = ["# 변이 시험 결과\n",
             "`oracle/mutation_check.py`가 생성했다. sm.py의 함수를 일부러 틀리게 바꾸고 check_sm.py의 검사가 위반을 보고하는지 본다.\n",
             f"시험 범위: {', '.join(f[0] for f in fams)}\n",
             f"변이 전 기준선의 위반 검사: {sorted(base) if base else '없음'}\n",
             "| 변이 | 위반을 보고한 검사 | 판정 |",
             "|---|---|---|"]
    blind = 0
    for label, mut in MUTATIONS:
        restore = mut()
        flagged = set()
        err = None
        try:
            for name, cap, n, optgen, names in fams:
                _, _, viol, _, _ = check_sm.run_family(name, cap, n, optgen, names)
                flagged |= {k for k, v in viol.items() if v}
        except Exception as ex:  # 변이가 예외를 일으키면 그대로 적는다
            err = f"{type(ex).__name__}: {ex}"
        finally:
            restore()
        if err:
            verdict = f"예외로 중단({err})"
            cell = ", ".join(sorted(flagged)) or "-"
        elif flagged:
            verdict = "검출됨"
            cell = ", ".join(sorted(flagged))
        else:
            verdict = "**검출 못 함(사각지대)**"
            cell = "-"
            blind += 1
        lines.append(f"| {label} | {cell} | {verdict} |")
        print(f"[{time.time() - t0:6.1f}s] {label}: {verdict} {cell}", flush=True)
    lines.append(f"\n검출하지 못한 변이: {blind}개 / {len(MUTATIONS)}개. 총 소요 {time.time() - t0:.0f}초.")
    text = "\n".join(lines) + "\n"
    if out_path:
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    return 0 if base == set() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
