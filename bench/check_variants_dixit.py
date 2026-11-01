"""Dixit·Khuteta 2017 재구현(해석별 정책 여섯 개)의 점검 (prereg/RQ6.md SP-5, WP6.3). AI(Claude)가 쓴 초안이며 사람의 검토 전이다.
실행: python3 -I bench/check_variants_dixit.py formal/rq6/variants-check-dixit.md

bench/check_variants_begum.py와 같은 방식이다. 변형은 오라클(O1)과 비교하지 않는다(불일치가 K1이 재는 대상이다).
  1. 옮긴 표의 정합성과 문헌 예제 재현: 인쇄된 추적(P0, P1, P2 스택, P3 실행, P4 스택)과 스택 순서 P2, P4, P1, P0은 여섯 정책이 모두 재현한다.
     스택의 실행은 release="max"에서만 인쇄된 순서대로 끝까지 가고 release="alloc"에서는 P3 뒤에서 막힌다(관찰).
  2. 인쇄된 스택 순서와 맞는 정렬 키 후보(도출 D10), 문장 그대로의 '<' 읽기가 예제 추적과 맞지 않음.
  3. 같은 해석의 두 번째 독립 구현(스택을 파이썬 리스트로 두고 매번 전체를 정렬하는 기계)과의 차등. 변이체로 점검이 비공허함을 보인다.
  4. 속성(도출 D8–D10): 실행한 순서의 되짚기, 같은 release에서 once ⇒ top ⇒ repeat, alloc ⇒ max의 안전 함의(변형 사이의 관계),
     스택 정렬·접두사 성질, 입력 불변, 계측 식. 작은 상태의 전수에서 top이 repeat와 판정이 갈리는 최소 예(D9. 안전 순서가 있음은 되짚기로 보인다)와
     실행 순서(프로세스 번호)에 대한 의존(D8).
오라클(O1)과의 비교(K1)와 등록된 입력군 위의 비용·시간(K2, K3)은 동결 전에 하지 않는다(prereg/RQ6.md §5). 여섯 해석 중 어느 것이 오라클(닫힘 계산)과
판정이 같은지는 이 점검에서 확인하지 않는다(어느 해석이 '대표'인지는 동결 뒤에 정하므로 그 전에 오라클 일치 여부를 보지 않는다. variants.md V-1). 도출 D7은
코드로 확인하지 않은 서술이다. 소규모 전수에 쓰는 oracle.banker.all_states는 상태를 나열하는 용도로만 쓰고 그 판정 함수는 부르지 않는다. 문헌 예제는 등록된 입력군이 아니다.
"""
from __future__ import annotations

import itertools
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "oracle"))

import oracle.banker as ob  # noqa: E402  (all_states만 사용한다)
from bench.check_variants_begum import pool_states  # noqa: E402  (등록된 입력군이 아님)
from bench.check_variants_wicaksono import replay_ok  # noqa: E402
from bench.literature import dixit2017 as X  # noqa: E402
from bench.ops import CountingOps, PlainOps  # noqa: E402
from bench.policies import banker as pb  # noqa: E402
from bench.policies.banker.variants.dixit2017 import DIXIT_POLICIES  # noqa: E402
from bench.state import BState  # noqa: E402

NAMES6 = tuple(cls.name for cls in DIXIT_POLICIES)
TAILS = ("once", "top", "repeat")


class _Log:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.checks = 0

    def check(self, cond: bool, what: str) -> bool:
        self.checks += 1
        if not cond:
            self.fails.append(what)
        return bool(cond)


# ---------------------------------------------------------------- 두 번째 독립 구현

def literal_dixit(total, alloc, need, avail, release: str, tail: str, mutation: str | None = None, key: str = "need-sum") -> dict:
    """스택을 파이썬 리스트(끝이 위)로 두고 넣을 때마다 전체를 정렬하는 기계. primary(삽입 방식)와 구조를 달리한다.
    스택 정리의 비교 횟수는 정렬이 아니라 '위에서부터 자기보다 큰 키를 만날 때까지'의 식으로 센다.
    key: 정렬 키("need-sum" 기본, "need-sq" Need 제곱합, "max-sum" Max 합). 앞의 둘 외에는 예제의 인쇄된 스택 순서와 맞는 후보다(D10).
    mutation: 점검의 비공허성을 보이려는 고의 오류.
      strict-fit    Need < Available(모든 성분이 엄격히 작음)일 때만 실행
      swap-release  release를 반대로(max ↔ alloc)
      no-sub        Available에서 Need를 빼지 않는다
      lifo-stack    스택을 정리하지 않는다(나중에 넣은 것이 위)
      desc-key      키가 큰 것이 위
      key-max       키를 Need 성분의 최댓값으로(예제의 인쇄된 스택 순서와 맞지 않는 키)
      tie-lifo      같은 키에서 나중에 넣은 것이 위
      tail-swap     tail을 바꾼다(once → top, top ↔ repeat)
    반환: dict(safe, unsafe, stack(위에서 아래로), counts)"""
    n, d = len(alloc), len(total)
    Available = list(avail)
    stack: list = []                      # 리스트의 끝이 위(top)
    seq: list = []
    kv: dict = {}
    c = dict(vec_cmp=0, sca_cmp=0, vec_add=0, iters=0, sort_cmp=0, key_add=0, pushes=0, rounds=0)

    def keyof(i: int) -> int:
        if mutation == "key-max":
            return max(need[i])
        if key == "need-sq":
            return sum(x * x for x in need[i])
        if key == "max-sum":
            return sum(alloc[i][j] + need[i][j] for j in range(d))
        return sum(need[i])

    def fits(i: int) -> bool:
        c["vec_cmp"] += 1
        for j in range(d):
            c["sca_cmp"] += 1
            blocked = (need[i][j] >= Available[j]) if mutation == "strict-fit" else (need[i][j] > Available[j])
            if blocked:
                return False
        return True

    def execute(i: int) -> None:
        if mutation != "no-sub":
            for j in range(d):
                Available[j] -= need[i][j]
        c["vec_add"] += 1
        give_max = (release == "max") != (mutation == "swap-release")
        for j in range(d):
            Available[j] += (alloc[i][j] + need[i][j]) if give_max else alloc[i][j]
        c["vec_add"] += 1
        seq.append(i)

    def push(i: int) -> None:
        k = keyof(i)
        kv[i] = k
        c["key_add"] += d - 1
        c["pushes"] += 1
        if mutation == "lifo-stack":
            stack.append(i)
            return
        above = sum(1 for e in stack if (kv[e] < k if mutation == "tie-lifo" else kv[e] <= k))
        c["sort_cmp"] += above + (1 if above < len(stack) else 0)
        stack.append(i)
        if mutation == "desc-key":
            stack.sort(key=lambda e: (kv[e], e))
        elif mutation == "tie-lifo":
            stack.sort(key=lambda e: (kv[e], -e), reverse=True)
        else:
            stack.sort(key=lambda e: (kv[e], e), reverse=True)

    for i in range(n):
        c["iters"] += 1
        if fits(i):
            execute(i)
        else:
            push(i)
    eff = {"once": "top", "top": "repeat", "repeat": "top"}[tail] if mutation == "tail-swap" else tail
    if eff == "top":
        while stack:
            j = stack[-1]
            c["iters"] += 1
            if fits(j):
                stack.pop()
                execute(j)
            else:
                break
    elif eff == "repeat":
        while stack:
            c["rounds"] += 1
            progress = False
            keep: list = []
            for j in reversed(stack):
                c["iters"] += 1
                if fits(j):
                    execute(j)
                    progress = True
                else:
                    keep.append(j)
            stack = list(reversed(keep))
            if not progress:
                break
    return {"safe": seq, "unsafe": bool(stack), "stack": list(reversed(stack)), "counts": c}


def parse(name: str) -> tuple[str, str]:
    _, rel, tail = name.split("-")
    return rel, tail


def lit_of(name: str, st: BState, mutation: str | None = None, key: str = "need-sum") -> dict:
    rel, tail = parse(name)
    return literal_dixit(st.total, st.alloc, st.need, st.avail, rel, tail, mutation, key)


def same(res, lit: dict, snap: dict) -> bool:
    if res.safe != lit["safe"] or res.unsafe != lit["unsafe"] or res.stack != lit["stack"]:
        return False
    c = lit["counts"]
    if snap.get("vec_cmp", 0) != c["vec_cmp"] or snap.get("sca_cmp", 0) != c["sca_cmp"] + c["sort_cmp"]:
        return False
    return all(snap.get(k, 0) == c[k] for k in ("vec_add", "iters", "sort_cmp", "key_add", "pushes", "rounds"))


def run_all(st: BState) -> dict:
    return {nm: pb.get(nm).run(st, CountingOps()) for nm in NAMES6}


# ---------------------------------------------------------------- 점검 본문

def check_registry(L: _Log) -> None:
    for cls in DIXIT_POLICIES:
        rel, tail = parse(cls.name)
        L.check(cls.name in pb.REGISTRY and pb.get(cls.name).release == rel and pb.get(cls.name).tail == tail, f"등록부의 {cls.name}")
    L.check(len(set(pb.REGISTRY)) == len(pb.REGISTRY), "등록부 이름 중복")
    L.check(len(NAMES6) == 6 and len(set(NAMES6)) == 6, "dixit 정책이 여섯 개가 아님")


def tables_consistent(maxc, alloc, need_printed, total, avail_printed, names) -> list[str]:
    bad: list[str] = []
    m = len(total)
    for i in range(len(maxc)):
        if tuple(maxc[i][j] - alloc[i][j] for j in range(m)) != tuple(need_printed[i]):
            bad.append(f"Need ≠ Max − Allocation ({names[i]})")
        if any(maxc[i][j] > total[j] for j in range(m)):
            bad.append(f"Max > 총량 ({names[i]})")
    av = tuple(total[j] - sum(r[j] for r in alloc) for j in range(m))
    if av != tuple(avail_printed):
        bad.append(f"총량 − ΣAllocation = {av} ≠ 인쇄된 Available {tuple(avail_printed)}")
    return bad


def check_fixture(L: _Log, info: dict) -> None:
    bad = tables_consistent(X.MAXC, X.ALLOC, X.NEED_PRINTED, X.TOTAL, X.AVAIL_PRINTED, X.NAMES)
    L.check(not bad, f"옮긴 표의 정합성 위반: {bad}")
    st, names = X.load()
    L.check(st.avail == list(X.AVAIL_PRINTED), f"load()의 Available {st.avail} ≠ {list(X.AVAIL_PRINTED)}")
    L.check([names[i] for i in range(5)] == [x for x in X.NAMES], "이름 순서")
    # 비공허성
    bad_alloc = tuple(X.ALLOC[:3]) + ((2, 1, 2),) + tuple(X.ALLOC[4:])
    L.check(len(tables_consistent(X.MAXC, bad_alloc, X.NEED_PRINTED, X.TOTAL, X.AVAIL_PRINTED, X.NAMES)) > 0, "비공허성: Allocation을 틀리게 한 표를 정합성 점검이 잡지 못함")
    bad_need = tuple(X.NEED_PRINTED[:4]) + ((0, 2, 5),)
    L.check(len(tables_consistent(X.MAXC, X.ALLOC, bad_need, X.TOTAL, X.AVAIL_PRINTED, X.NAMES)) > 0, "비공허성: Need를 틀리게 한 표를 정합성 점검이 잡지 못함")
    info["fixture"] = {"avail": st.avail}


def check_example(L: _Log, info: dict) -> None:
    st, names = X.load()
    out: dict = {}
    for nm in NAMES6:
        ops = CountingOps()
        r = pb.get(nm).run(st, ops, want_trace=True)
        rel, tail = parse(nm)
        passes = [t for t in r.trace if t["phase"] == "pass"]
        got = tuple((names[t["i"]], t["act"]) for t in passes)
        want = X.TRACE_PRINTED
        L.check(got == want, f"{nm}: 훑기의 추적이 인쇄된 추적과 다름 {got}")
        stack_after_pass = tuple(names[j] for j in passes[-1]["stack"])
        L.check(stack_after_pass == X.STACK_PRINTED, f"{nm}: 훑기 뒤의 스택 {stack_after_pass} ≠ 인쇄된 {X.STACK_PRINTED}")
        final = r.trace[-1]["avail"]
        out[nm] = {"seq": [names[i] for i in r.safe], "unsafe": r.unsafe, "stack": [names[j] for j in r.stack], "final_avail": final,
                   "after_p3": next(t["avail"] for t in passes if names[t["i"]] == "P3"), "ops": ops.snapshot()}
    # 해석 판별: release="max"에서만 스택이 인쇄된 순서(위에서부터)로 모두 실행된다
    full = ["P3"] + list(X.STACK_PRINTED)
    for nm in ("dixit-max-top", "dixit-max-repeat"):
        L.check(out[nm]["seq"] == full and not out[nm]["unsafe"] and tuple(out[nm]["final_avail"]) == X.TOTAL,
                f"{nm}: 스택이 인쇄된 순서로 모두 실행되고 끝난 뒤 Available이 총량이어야 함 {out[nm]}")
    L.check(out["dixit-max-once"]["seq"] == ["P3"] and out["dixit-max-once"]["unsafe"] and out["dixit-max-once"]["stack"] == list(X.STACK_PRINTED),
            "dixit-max-once: P3만 실행하고 스택이 남아야 함")
    for nm in ("dixit-alloc-once", "dixit-alloc-top", "dixit-alloc-repeat"):
        L.check(out[nm]["seq"] == ["P3"] and out[nm]["unsafe"] and out[nm]["stack"] == list(X.STACK_PRINTED)
                and out[nm]["after_p3"] == [2, 1, 1], f"{nm}: P3 뒤 Available (2, 1, 1)에서 막혀야 함 {out[nm]}")
    # P3 단계는 Need = Available라서 '≤'로만 통과한다(문장 그대로의 '<' 읽기는 인쇄된 추적과 맞지 않는다)
    lit_strict = literal_dixit(st.total, st.alloc, st.need, st.avail, "max", "repeat", "strict-fit")
    L.check(lit_strict["safe"][:1] != [3], "'<' 읽기가 인쇄된 추적(첫 실행이 P3)과 같음 — 인쇄된 추적을 가르지 못함")
    out["strict"] = {"seq": [names[i] for i in lit_strict["safe"]], "unsafe": lit_strict["unsafe"]}
    # 정렬 키 후보 (D10): 인쇄된 스택 순서를 재현하는가
    cands = {
        "Need 성분의 합": lambda i: sum(st.need[i]),
        "Need의 제곱합": lambda i: sum(x * x for x in st.need[i]),
        "Max 성분의 합": lambda i: sum(st.alloc[i][j] + st.need[i][j] for j in range(3)),
        "Need 성분의 최댓값": lambda i: max(st.need[i]),
        "Need의 사전식 순서": lambda i: tuple(st.need[i]),
        "Allocation 성분의 합": lambda i: sum(st.alloc[i]),
        "Need의 최솟값": lambda i: min(st.need[i]),
    }
    stacked = [i for i in range(5) if names[i] != "P3"]
    key_rows = []
    for label, f in cands.items():
        order = tuple(names[i] for i in sorted(stacked, key=lambda i: (f(i), i)))
        key_rows.append((label, order, order == X.STACK_PRINTED))
    L.check(any(ok for _l, _o, ok in key_rows) and any(not ok for _l, _o, ok in key_rows), "키 후보 점검이 비공허하지 않음(맞는 것과 아닌 것이 모두 있어야 함)")
    L.check([ok for l, _o, ok in key_rows if l in ("Need 성분의 합", "Need의 제곱합", "Max 성분의 합")] == [True, True, True], "Need 합·제곱합·Max 합이 인쇄된 스택 순서를 재현해야 함")
    L.check(all(not ok for l, _o, ok in key_rows if l in ("Need 성분의 최댓값", "Need의 사전식 순서", "Allocation 성분의 합")), "최댓값·사전식·Allocation 합은 인쇄된 스택 순서를 재현하면 안 됨")
    out["keys"] = key_rows
    # 같은 입력에서 교재식 구현의 비용(관찰)
    base = {}
    for nm in ("textbook-restart", "textbook-sweep"):
        o = CountingOps()
        pb.get(nm).is_safe(st, o)
        base[nm] = o.snapshot()
    out["baseline"] = base
    L.check(st.alloc == [list(r) for r in X.ALLOC] and st.avail == list(X.AVAIL_PRINTED), "예제 실행이 입력 상태를 바꿈")
    info["example"] = out


def check_differential(L: _Log, info: dict) -> None:
    t0 = time.time()
    pool = pool_states(20261101, small_stride=40, wide=1500)
    bad = {nm: 0 for nm in NAMES6}
    cov = {"훑기에서 모두 실행(스택 비어 있음)": 0, "스택에 남아 tail이 일한다": 0, "tail에서 모두 실행": 0, "tail에서 막힘(불안전)": 0,
           "repeat가 2번 이상 훑음": 0, "스택 정리에서 키가 같은 프로세스가 둘 이상": 0, "스택 정리에서 비교를 2번 이상 쓴 삽입이 있음": 0, "d = 1": 0}
    for st in pool:
        for nm in NAMES6:
            ops = CountingOps()
            res = pb.get(nm).run(st, ops)
            if not same(res, lit_of(nm, st), ops.snapshot()):
                bad[nm] += 1
            if nm == "dixit-max-repeat":
                stk0 = pb.get("dixit-max-once").run(st, PlainOps())
                if not stk0.stack:
                    cov["훑기에서 모두 실행(스택 비어 있음)"] += 1
                else:
                    cov["스택에 남아 tail이 일한다"] += 1
                    if res.unsafe:
                        cov["tail에서 막힘(불안전)"] += 1
                    else:
                        cov["tail에서 모두 실행"] += 1
                    if res.counts["rounds"] >= 2:
                        cov["repeat가 2번 이상 훑음"] += 1
                    ks = [sum(st.need[p]) for p in stk0.stack]
                    if len(set(ks)) < len(ks):
                        cov["스택 정리에서 키가 같은 프로세스가 둘 이상"] += 1
                    if stk0.counts["sort_cmp"] > max(0, stk0.counts["pushes"] - 1):
                        cov["스택 정리에서 비교를 2번 이상 쓴 삽입이 있음"] += 1
                if st.m == 1:
                    cov["d = 1"] += 1
    total_bad = sum(bad.values())
    L.check(total_bad == 0, f"차등 불일치 {bad} / {len(pool)}×6")
    for k, v in cov.items():
        L.check(v > 0, f"차등 입력이 분기 '{k}'를 지나가지 않음")
    info["diff"] = {"states": len(pool), "runs": len(pool) * 6, "bad": bad, "cov": cov, "seconds": time.time() - t0}


def check_mutants(L: _Log, info: dict) -> None:
    pool = pool_states(777, small_stride=60, wide=600)
    out = []
    # 변이체는 해당 정책에 대해서만 의미가 있으므로 정책별로 넣어 본다
    plan = {"strict-fit": NAMES6, "swap-release": NAMES6, "no-sub": NAMES6, "lifo-stack": NAMES6, "desc-key": NAMES6, "key-max": NAMES6,
            "tie-lifo": NAMES6, "tail-swap": NAMES6}
    for mut, names in plan.items():
        caught_by = {}
        for nm in names:
            caught = 0
            for st in pool:
                ops = CountingOps()
                res = pb.get(nm).run(st, ops)
                if not same(res, lit_of(nm, st, mut), ops.snapshot()):
                    caught += 1
            caught_by[nm] = caught
        L.check(sum(caught_by.values()) > 0, f"변이체 {mut}를 차등 점검이 잡지 못함")
        out.append((mut, caught_by, len(pool)))
    info["mutants"] = out


def check_properties(L: _Log, info: dict) -> None:
    pool = pool_states(424242, small_stride=50, wide=800)
    keys = ("replay", "chain", "conservative", "stack_sorted", "top_prefix", "mutate", "plain", "formula", "partition")
    props = {k: 0 for k in keys}
    for st in pool:
        n, d = st.n, st.m
        snap = (list(map(list, st.alloc)), list(map(list, st.need)), list(st.avail), list(st.total))
        R = run_all(st)
        for nm, r in R.items():
            if not replay_ok(st.alloc, st.need, st.avail, r.safe):
                props["replay"] += 1
            if len(set(r.safe)) != len(r.safe) or set(r.safe) & set(r.stack) or len(r.safe) + len(r.stack) != n:
                props["partition"] += 1
            r2 = pb.get(nm).run(st, PlainOps())
            if (r2.safe, r2.unsafe, r2.stack) != (r.safe, r.unsafe, r.stack):
                props["plain"] += 1
        # 같은 release에서 once ⇒ top ⇒ repeat (안전 함의)
        for rel in ("max", "alloc"):
            s_once, s_top, s_rep = (not R[f"dixit-{rel}-{t}"].unsafe for t in TAILS)
            if (s_once and not s_top) or (s_top and not s_rep):
                props["chain"] += 1
        # alloc ⇒ max (같은 tail에서 alloc 읽기가 안전이면 max 읽기도 안전)
        for t in TAILS:
            if (not R[f"dixit-alloc-{t}"].unsafe) and R[f"dixit-max-{t}"].unsafe:
                props["conservative"] += 1
        # 스택 정리: 훑기 뒤 스택은 (Need 합, 번호) 오름차순(위에서 아래로)
        for rel in ("max", "alloc"):
            stk = R[f"dixit-{rel}-once"].stack
            if stk != sorted(stk, key=lambda p: (sum(st.need[p]), p)):
                props["stack_sorted"] += 1
            # top은 훑기 뒤 스택의 위에서부터 접두사를 실행한다
            once, top = R[f"dixit-{rel}-once"], R[f"dixit-{rel}-top"]
            k = len(top.safe) - len(once.safe)
            if top.safe[:len(once.safe)] != once.safe or not (0 <= k <= len(once.stack)) or top.safe[len(once.safe):] != once.stack[:k]:
                props["top_prefix"] += 1
            # 계측 식
            c = once.counts
            ok = (c["pushes"] + len(once.safe) == n and c["key_add"] == c["pushes"] * (d - 1) and 0 <= c["sort_cmp"] <= c["pushes"] * (c["pushes"] - 1) // 2)
            for t in TAILS:
                rt = R[f"dixit-{rel}-{t}"]
                cnt = rt.counts
                ops_t = CountingOps()
                pb.get(f"dixit-{rel}-{t}").run(st, ops_t)
                sn = ops_t.snapshot()
                ok &= (sn["vec_add"] == 2 * len(rt.safe) and sn["iters"] == sn["vec_cmp"] and cnt["executed"] == len(rt.safe))
                if t == "once":
                    ok &= (sn["vec_cmp"] == n and cnt["rounds"] == 0)
                elif t == "top":
                    ok &= (sn["vec_cmp"] == n + k + (1 if top.unsafe else 0) and cnt["rounds"] == 0)
                else:
                    ok &= ((cnt["rounds"] == 0) == (not once.stack) and sn["vec_cmp"] >= n + len(once.stack))
            if not ok:
                props["formula"] += 1
        if snap != (list(map(list, st.alloc)), list(map(list, st.need)), list(st.avail), list(st.total)):
            props["mutate"] += 1
    labels = {"replay": "안전 순서(실행한 순서)가 교재식 되짚기에서 실행 불가",               "chain": "같은 release에서 once ⇒ top ⇒ repeat의 안전 함의 위반", "conservative": "alloc 읽기가 안전인데 같은 tail의 max 읽기는 불안전",
              "stack_sorted": "훑기 뒤 스택이 (Need 합, 번호) 오름차순이 아님", "top_prefix": "top이 훑기 뒤 스택의 위에서부터 접두사를 실행하지 않음",
              "mutate": "입력 상태 변경", "plain": "계측·비계측 결과 불일치", "formula": "계측 식 위반(vec_cmp, vec_add, iters, pushes, key_add, sort_cmp, rounds)",
              "partition": "실행한 집합과 스택이 겹치거나 합쳐도 전체가 아님"}
    for key, cnt in props.items():
        L.check(cnt == 0, f"속성 위반 {labels[key]}: {cnt}건")
    info["props"] = props
    info["prop_labels"] = labels
    info["prop_states"] = len(pool)


def collect_derivations(L: _Log, info: dict) -> None:
    """도출 D8(실행 순서 의존), D9(top의 최소 반례), D10(키 후보가 판정을 가르는가). 작은 상태의 전수와 점검 입력. 오라클은 쓰지 않는다."""
    out: dict = {}
    # D9: top이 불안전이라 하는데 교재식 안전 순서가 있는(되짚기 증명서로 확인) 최소 예. n이 작은 것, 총량 합이 작은 것부터. 키가 같은 프로세스가 없는 예를 따로 찾는다.
    def ex_search(distinct: bool):
        for n, total in [(2, (1, 1)), (2, (2, 2)), (3, (1, 1)), (3, (2, 1)), (3, (1, 1, 1)), (3, (2, 2)), (3, (3, 2)), (3, (3, 3)), (4, (1, 1)), (4, (2, 1))]:
            tried = 0
            for b in ob.all_states(n, total):
                st = BState.from_oracle(b)
                tried += 1
                top = pb.get("dixit-max-top").run(st, PlainOps())
                if not top.unsafe:
                    continue
                rep = pb.get("dixit-max-repeat").run(st, PlainOps())
                if rep.unsafe or len(rep.safe) != st.n:
                    continue
                if distinct:
                    ks = [sum(st.need[p]) for p in top.stack]
                    if len(set(ks)) != len(ks):
                        continue
                return {"n": n, "total": total, "alloc": st.alloc, "need": st.need, "avail": st.avail, "stack": top.stack, "executed": top.safe, "tried": tried}
        return None
    out["d9_any"] = ex_search(False)
    out["d9_distinct"] = ex_search(True)
    L.check(out["d9_any"] is not None and out["d9_distinct"] is not None, "D9: top이 불안전이라 하나 안전 순서가 있는 예를 찾지 못함")
    for key in ("d9_any", "d9_distinct"):
        e = out[key]
        if e is not None:
            # 예가 정말 반례인지 증명서로 확인: repeat가 낸 실행 순서가 모든 프로세스를 끝내는 안전 순서임을 되짚기로 보이고, top과 once는 불안전을 돌려준다
            st = BState.make(e["total"], e["alloc"], e["need"])
            rep = pb.get("dixit-max-repeat").run(st, PlainOps())
            e["certificate"] = list(rep.safe)
            L.check(len(rep.safe) == st.n and replay_ok(st.alloc, st.need, st.avail, rep.safe)
                    and pb.get("dixit-max-top").run(st, PlainOps()).unsafe and pb.get("dixit-max-once").run(st, PlainOps()).unsafe, f"D9 예({key})가 반례가 아님")
    # D8: 프로세스 번호를 바꾸면 판정이 달라지는가(소규모 전수의 일부)
    perm_dep = {nm: 0 for nm in NAMES6}
    examined = 0
    small = []
    for n, total, stride in [(3, (1, 1, 1), 1), (3, (2, 2), 3)]:
        small += [BState.from_oracle(b) for k, b in enumerate(ob.all_states(n, total)) if k % stride == 0]
    perm_example = None
    for st in small:
        examined += 1
        verd = {nm: set() for nm in NAMES6}
        for perm in itertools.permutations(range(st.n)):
            s2 = BState(list(st.total), [st.alloc[p] for p in perm], [st.need[p] for p in perm], list(st.avail))
            for nm in NAMES6:
                verd[nm].add(pb.get(nm).run(s2, PlainOps()).unsafe)
        for nm in NAMES6:
            if len(verd[nm]) > 1:
                perm_dep[nm] += 1
                if nm == "dixit-alloc-repeat" and perm_example is None:
                    perm_example = st
    L.check(perm_dep["dixit-max-repeat"] == 0, f"D8: max-repeat의 판정이 프로세스 번호에 의존함({perm_dep['dixit-max-repeat']}건). D7의 서술대로면 의존하지 않아야 함")
    L.check(perm_dep["dixit-alloc-repeat"] > 0 and perm_dep["dixit-max-once"] > 0 and perm_dep["dixit-max-top"] > 0,
            "D8: alloc-repeat, max-once, max-top의 판정이 번호에 의존하는 상태를 찾지 못함")
    out["d8"] = {"examined": examined, "perm_dep": perm_dep}
    if perm_example is not None:
        out["d8_example"] = {"total": perm_example.total, "alloc": perm_example.alloc, "need": perm_example.need, "avail": perm_example.avail}
        # 예에서 어느 번호 순서가 안전/불안전인지
        vs = {}
        for perm in itertools.permutations(range(perm_example.n)):
            s2 = BState(list(perm_example.total), [perm_example.alloc[p] for p in perm], [perm_example.need[p] for p in perm], list(perm_example.avail))
            vs[perm] = not pb.get("dixit-alloc-repeat").run(s2, PlainOps()).unsafe
        out["d8_example"]["verdicts"] = vs
        cert = next((list(o) for o in itertools.permutations(range(perm_example.n))
                     if replay_ok(perm_example.alloc, perm_example.need, perm_example.avail, list(o))), None)
        out["d8_example"]["certificate"] = cert
        L.check(cert is not None, "D8 예: 교재식 안전 순서(증명서)를 찾지 못함")
    # D10: 인쇄된 예제와 모두 맞는 키들이 top의 판정을 가르는가(점검 입력)
    pool = pool_states(99, small_stride=60, wide=500)
    diffs = {"need-sq": 0, "max-sum": 0}
    n_top = 0
    for st in pool:
        base = literal_dixit(st.total, st.alloc, st.need, st.avail, "max", "top")["unsafe"]
        n_top += 1
        for key in diffs:
            if literal_dixit(st.total, st.alloc, st.need, st.avail, "max", "top", None, key)["unsafe"] != base:
                diffs[key] += 1
    L.check(diffs["need-sq"] > 0 or diffs["max-sum"] > 0, "D10: 예제와 맞는 다른 키가 top의 판정을 가른 입력을 찾지 못함")
    out["d10"] = {"states": n_top, "diffs": diffs}
    info["deriv"] = out


def fmt_state(e: dict) -> str:
    return f"n = {e['n']}, 총량 {e['total']}, Allocation {e['alloc']}, Need {e['need']}, Available {e['avail']}"


def main(out_path: str | None) -> int:
    t0 = time.time()
    L = _Log()
    info: dict = {}
    check_registry(L)
    check_fixture(L, info)
    check_example(L, info)
    check_properties(L, info)
    check_mutants(L, info)
    check_differential(L, info)
    collect_derivations(L, info)
    ex = info["example"]
    d = info["diff"]
    dv = info["deriv"]

    lines = ["# 문헌 변형 재구현 점검 결과: Dixit·Khuteta 2017 (R6-04, 해석별 정책 여섯 개)\n",
             "`bench/check_variants_dixit.py`가 쓴 결과다. AI(Claude)가 작성한 초안이며 사람의 검토 전이다. 변형은 오라클과 비교하지 않는다"
             "(불일치가 K1이 재는 대상이다). 문헌 예제 재현, 같은 해석의 두 번째 독립 구현과의 차등, 속성을 본다. "
             "이 점검은 오라클도, 오라클의 정의(닫힘 계산)를 따로 옮긴 함수도 쓰지 않는다. 아래 '관찰'은 문헌 예제의 재현 결과이며 주장 판정이 아니다. "
             "논문의 숫자는 제3자 사본(SlideShare)의 본문을 도구가 읽어 낸 텍스트에서 옮겼고 저널 PDF와는 아직 대조하지 않았다.\n"]
    lines.append("## 1. 옮긴 표의 정합성과 예제 재현\n")
    lines.append(f"Need = Max − Allocation(다섯 행 모두), Max ≤ 총량, 총량 − ΣAllocation = {info['fixture']['avail']}(인쇄된 Available과 같음). "
                 "옮긴 값을 일부러 틀리게 한 표 둘을 이 정합성 점검이 잡는다(비공허성).\n")
    lines.append("여섯 정책이 예제에서 낸 결과다. 훑기의 추적(P0·P1 스택, P2 스택과 정리, P3 실행, P4 스택과 정리)과 훑기 뒤의 스택 순서(위에서 P2, P4, P1, P0)는 "
                 "여섯 정책이 모두 인쇄된 것과 같다(P3을 실행하기 전에는 release와 tail이 영향을 주지 않고, P3 뒤의 P4 판단은 이 예제에서는 두 release에서 같다). 달라지는 것은 P3 뒤의 Available과 스택의 처리다.\n")
    lines.append("| 정책 | 실행한 순서 | 스택에 남음(위→아래) | P3 실행 뒤 Available | 끝났을 때 Available | 판정 |")
    lines.append("|---|---|---|---|---|---|")
    for nm in NAMES6:
        o = ex[nm]
        lines.append(f"| {nm} | {', '.join(o['seq'])} | {', '.join(o['stack']) or '—'} | {tuple(o['after_p3'])} | {tuple(o['final_avail'])} | {'불안전' if o['unsafe'] else '안전'} |")
    lines.append("")
    lines.append("논문은 스택의 프로세스가 '위에서부터 실행된다'고 쓰고 단계별 Available도 최종 안전 순서도 인쇄하지 않는다. 위 표의 관찰은 다음과 같다. "
                 "(가) release=\"max\"(Allocation을 받은 뒤의 보유량으로 읽음)에서는 top과 repeat이 스택을 인쇄된 순서(P2, P4, P1, P0) 그대로 모두 실행하고 "
                 f"끝난 뒤 Available이 총량 {X.TOTAL}이 된다. (나) release=\"alloc\"(인쇄된 식을 글자 그대로 읽음)에서는 P3을 실행한 뒤 Available이 (2, 1, 1)로 줄어 "
                 "스택의 어느 프로세스도 실행되지 못한다. 논문이 스택의 프로세스가 실행된다고 쓰므로 (나)의 읽기는 논문의 서술과 맞지 않는다. 이는 AI의 해석이며 "
                 "저자의 뜻을 확인한 것이 아니다.\n")
    lines.append(f"문장 그대로의 '미만' 읽기(Need < Available, 모든 성분이 엄격히 작음)에서는 첫 단계의 P3(Need = Available)이 실행되지 않아 인쇄된 추적과 맞지 않는다"
                 f"(변이체 strict-fit의 결과: 실행한 순서 {ex['strict']['seq'] or '(없음)'}, 불안전 {'예' if ex['strict']['unsafe'] else '아니오'}). 그래서 비교는 '≤'로 읽었다.\n")
    lines.append("### 1.1 인쇄된 스택 순서와 맞는 정렬 키 (도출 D10, AI)\n")
    lines.append("논문은 스택을 '필요량이 작은 것이 위'로 정리한다고만 쓰고 필요량 벡터의 크기를 비교하는 규칙을 쓰지 않는다. 예제의 인쇄된 순서(P2, P4, P1, P0)를 재현하는 키 후보다.\n")
    lines.append("| 키 | 스택 순서(위→아래, 같은 키는 번호 순) | 인쇄된 순서와 같은가 |")
    lines.append("|---|---|---|")
    for label, order, ok in ex["keys"]:
        lines.append(f"| {label} | {', '.join(order)} | {'예' if ok else '아니오'} |")
    lines.append("")
    d10 = dv["d10"]
    lines.append(f"예제와 맞는 키가 여럿이므로 예제로는 키를 정할 수 없다. 이 구현은 가장 단순한 'Need 성분의 합'을 썼다. 점검 입력 {d10['states']}개에서 max-top의 판정이 "
                 f"Need 합 대신 제곱합을 쓰면 {d10['diffs']['need-sq']}개, Max 합을 쓰면 {d10['diffs']['max-sum']}개에서 달라졌다(변형 사이의 비교이며 오라클과의 비교가 아니다).\n")
    lines.append("### 1.2 관찰: 같은 입력에서 비용\n")
    lines.append("논문의 주장은 그림 2의 실행 시간(평균 약 9%)뿐이고 조건이 없어 재현하지 못한다. 아래는 이 예제에서 센 값이며 K2의 결과가 아니다.\n")
    lines.append("| 실행 | vec_cmp | sca_cmp | vec_add | iters | sort_cmp | key_add |")
    lines.append("|---|---|---|---|---|---|---|")
    for nm in NAMES6:
        s = ex[nm]["ops"]
        lines.append(f"| {nm} | {s.get('vec_cmp', 0)} | {s.get('sca_cmp', 0)} | {s.get('vec_add', 0)} | {s.get('iters', 0)} | {s.get('sort_cmp', 0)} | {s.get('key_add', 0)} |")
    for nm in ("textbook-restart", "textbook-sweep"):
        s = ex["baseline"][nm]
        lines.append(f"| {nm} | {s.get('vec_cmp', 0)} | {s.get('sca_cmp', 0)} | {s.get('vec_add', 0)} | {s.get('iters', 0)} | — | — |")
    lines.append("")
    lines.append("`sca_cmp`는 Need ≤ Available 확인의 스칼라 비교(단락 평가)와 스택 정리의 키 비교(`sort_cmp`)를 더한 값이다. 교재식 구현의 `vec_add`는 끝낸 프로세스마다 1번이고 "
                 "이 알고리즘은 Available에서 Need를 빼고 되돌리는 2번이다. 교재식 구현에는 정렬이 없다.\n")
    lines.append("## 2. 두 번째 독립 구현과의 차등\n")
    lines.append("스택을 파이썬 리스트(끝이 위)로 두고 넣을 때마다 전체를 정렬하는 기계(`literal_dixit`)와 여섯 정책 각각을 비교한다. 정리의 비교 횟수는 "
                 "'위에서부터 자기보다 큰 키를 만날 때까지'의 식으로 센다. 비교 항목은 실행한 순서, 불안전 여부, 남은 스택, 계측 계수(vec_cmp, sca_cmp, vec_add, iters, sort_cmp, key_add, pushes, rounds)다. "
                 f"입력은 문헌 예제와 소규모 전수 일부, 층화 무작위(F-rand형) 일부, 경계 상태, 값이 큰 무작위 상태를 합한 {d['states']:,}개이고 여섯 정책으로 {d['runs']:,}회 실행했다"
                 f"(등록된 입력군이 아니다). 불일치 {sum(d['bad'].values())}건. 시간 {d['seconds']:.1f}초.\n")
    lines.append("| 분기(dixit-max-repeat 기준) | 입력 수 |")
    lines.append("|---|---|")
    for k, v in d["cov"].items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("## 3. 속성과 변이체\n")
    lines.append(f"속성은 {info['prop_states']}개 상태에서 여섯 정책 모두에 대해 본다.\n")
    lines.append("| 속성 | 위반 |")
    lines.append("|---|---|")
    for key, cnt in info["props"].items():
        lines.append(f"| {info['prop_labels'][key]} | {cnt} |")
    lines.append("")
    lines.append("변이체는 두 번째 구현에 넣은 오류다. 표는 정책별로 차등 점검이 잡은 입력 수이며 모든 변이체를 어느 정책에서든 잡았는지가 점검 대상이다(어떤 변이체는 특정 정책에서만 결과가 달라진다).\n")
    lines.append("| 변이체 | " + " | ".join(n.replace("dixit-", "") for n in NAMES6) + " | 입력 수 |")
    lines.append("|---|" + "---|" * 7)
    for mut, caught_by, total in info["mutants"]:
        lines.append(f"| {mut} | " + " | ".join(str(caught_by[n]) for n in NAMES6) + f" | {total} |")
    lines.append("")
    lines.append("## 4. 도출 (AI, 사람 검토 대기)\n")
    lines.append("- **D7 (max-repeat의 판정, 코드로 확인하지 않음)**: release=\"max\"이고 tail=\"repeat\"인 읽기는 안 끝난 프로세스를 되풀이해 훑고 진전이 없을 때 멈추므로 "
                 "끝낸 집합이 닫힘(순서와 무관한 가장 큰 완료 가능 집합)이고, 따라서 판정이 교재식 닫힘 계산(`docs/rq6/reference.md` §2)과 같을 것이다. "
                 "정렬된 스택은 비용과 안전 순서만 바꾸고 판정은 바꾸지 않을 것이다. 이는 도출이며 증명하지 않았고, 동결 전에 변형의 판정을 오라클·닫힘 계산과 대조하지 않는 규칙 때문에 "
                 "코드로도 확인하지 않았다(동결 뒤에 확인한다). 이 점검이 본 간접 증거는 아래 D8의 '번호 순열에 대해 max-repeat의 판정이 변하지 않음'뿐이다.")
    d8 = dv["d8"]
    lines.append(f"- **D8 (실행 순서 의존)**: 프로세스 번호를 모든 순열로 바꿔 판정이 달라지는 상태의 수(소규모 전수의 일부 {d8['examined']}개 중): "
                 + ", ".join(f"{n} {c}" for n, c in d8["perm_dep"].items())
                 + ". max-repeat는 0이다(D7의 서술과 맞는다). 반면 훑기를 번호 순으로 한 번만 하는 읽기(once)와 스택 위만 보는 읽기(top)는 번호에 의존하고, "
                 "release=\"alloc\"의 repeat도 의존한다(Available이 줄어들 수 있어 실행 순서에 따라 갈린다).")
    if "d8_example" in dv:
        e = dv["d8_example"]
        safe_perms = [p for p, v in e["verdicts"].items() if v]
        unsafe_perms = [p for p, v in e["verdicts"].items() if not v]
        lines.append(f"  - alloc-repeat의 예: 총량 {e['total']}, Allocation {e['alloc']}, Need {e['need']}, Available {e['avail']}. 번호 순열 {len(safe_perms)}개에서는 안전, "
                     f"{len(unsafe_perms)}개에서는 불안전이다. 이 상태에는 교재식 안전 순서 {e['certificate']}가 있다(되짚기로 확인한 증명서).")
    for key, label in (("d9_any", "최소 예(키가 같은 프로세스가 있을 수 있음)"), ("d9_distinct", "키가 모두 다른 최소 예")):
        e = dv[key]
        if e:
            lines.append(f"- **D9 (top이 불안전이라 하는데 교재식 안전 순서가 있음: 거짓 불안전의 최소 예)**, {label}: {fmt_state(e)}. 훑기에서 실행한 뒤 스택의 위(번호 {e['stack'][0]})가 실행되지 못해 "
                         f"top은 불안전을 돌려주지만 repeat는 모두 끝내고 그 실행 순서 {e['certificate']}가 교재식 안전 순서임을 되짚기로 확인했다(스택 {e['stack']}). 같은 (n, 총량)의 열거 순서에서 {e['tried']}번째 상태다.")
    lines.append("  Begum 외의 D1(`variants-derivations.md`)과 같은 종류의 도출이다: 가장 작다고 이름 붙은 필요량이 실행 가능한 프로세스를 가리지 못한다(벡터 필요량은 전순서가 아니다).")
    lines.append("- **D10**: 위 §1.1.\n")
    status = "모두 통과" if not L.fails else f"실패 {len(L.fails)}건"
    lines.append(f"점검 {L.checks}개: {status}. 총 시간 {time.time() - t0:.0f}초.\n")
    if L.fails:
        lines.append("### 실패 목록\n")
        lines += [f"- {x}" for x in L.fails[:60]]
        lines.append("")
    lines.append("## 범위와 한계\n")
    lines.append("- 이 점검은 '구현이 논문의 서술(의사코드 네 줄과 예제 설명)을 옮긴 해석과 같다'는 것과 '논문 예제를 재현한다'는 것만 본다. 해석이 저자의 뜻과 같다는 보장은 없다. "
                 "논문의 의사코드에는 스택 처리, 갱신식의 첨자, 정렬 키, 종료 조건이 없어 여섯 정책은 서로 다른 보완이다(docs/rq6/variants.md §5.2의 해석 목록).")
    lines.append("- 두 번째 구현은 같은 사람이 같은 이해로 쓴 것이다. 구조가 달라 옮기다 생기는 실수는 잡지만 해석의 오류는 잡지 못한다.")
    lines.append("- 논문의 값은 제3자 사본의 본문을 도구가 읽어 낸 텍스트에서 옮겼다. 값 사이의 중복(Need = Max − Allocation, 총량)으로 정합성을 점검했으나 저널 인쇄본과의 일치를 보장하지는 않는다.")
    lines.append("- 논문의 정량 주장(그림 2, 평균 약 9%)은 곡선 값과 실행 조건이 없어 재현하지 못한다. 이 점검은 K2·K3를 재지 않는다.")
    lines.append("- 논문의 추상은 실행 중 자원 수를 바꿀 수 있다고 쓰나 알고리즘, 표, 예제에 그 내용이 없다. 구현하지 않았다.")
    lines.append("- 소규모 전수에 쓴 oracle.banker.all_states는 상태를 나열하는 데만 썼고 오라클의 판정은 부르지 않았다. 오라클(O1)과의 비교와 등록된 입력군 위의 비용·시간은 동결 전에 하지 않았다.")
    text = "\n".join(lines) + "\n"
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(f"점검 {L.checks}개, 실패 {len(L.fails)}건, {time.time() - t0:.0f}초")
    for x in L.fails[:20]:
        print("  실패:", x)
    return 1 if L.fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
